"""This file defines the API routes."""

# pylint: disable = no-name-in-module

from flask import Flask, Response, request, jsonify, abort
import psycopg2
from psycopg2.errors import ForeignKeyViolation

from database import get_db_connection

app = Flask(__name__)
conn = get_db_connection()


@app.route("/", methods=["GET"])
def index() -> Response:
    """Returns a welcome message."""
    return jsonify({
        "title": "Clown API",
        "description": "Welcome to the world's first clown-rating API."
    })


@app.route("/clown", methods=["GET", "POST"])
def get_clowns() -> Response:
    """Returns a list of clowns in response to a GET request;
    Creates a new clown in response to a POST request."""
    if request.method == "GET":
        ordered_data = []
        with conn.cursor() as cur:
            sql_query = "SELECT clown.clown_id, clown.clown_name, speciality_name FROM clown JOIN speciality ON clown.speciality_id = speciality.speciality_id"
            cur.execute(sql_query)
            data = cur.fetchall()
            for d in data:
                score = score_calculator(conn, d['clown_id'])
                if score != 0 or score != None:
                    d['avg_score'] = score[0]['score']
                count = number_of_ratings(conn, d["clown_id"])
                if score != 0 or score != None:
                    d['number_of_reviews'] = count[0]['count']
            if 'order' in request.args:
                for d in data:
                    if request.args['order'] == 'descending':
                        while len(data) != 0:
                            if d['avg_score'] == max(data, key=lambda x: x['avg_score']):
                                ordered_data.append(d)
                                data.remove(d)
                    if request.args['order'] == 'ascending':
                        while len(data) != 0:
                            if d['avg_score'] == min(data, key=lambda x: x['avg_score']):
                                ordered_data.append(d)
                                data.remove(d)
                return jsonify(ordered_data)
            return jsonify(data)

    else:
        data = request.json
        try:
            if "clown_name" not in data or "speciality_id" not in data:
                raise KeyError("New clowns need both a name and a speciality.")
            if not isinstance(data["speciality_id"], int):
                raise ValueError("Clown speciality must be an integer.")

            with conn.cursor() as cur:
                cur.execute("""INSERT INTO clown
                                 (clown_name, speciality_id)
                               VALUES (%s, %s)
                               RETURNING *;""",
                            (data["clown_name"], data["speciality_id"]))
                new_clown = cur.fetchone()
                conn.commit()
            return jsonify(new_clown), 201
        except (KeyError, ValueError, ForeignKeyViolation) as err:
            print(err.args[0])
            conn.rollback()
            return jsonify({
                "message": err.args[0]
            }), 400


@app.route("/clown/<int:id>", methods=["GET", "POST"])
def get_clowns_by_id(id) -> Response:
    """Returns clown by ID number"""
    if request.method == "GET":
        if not isinstance(id, int):
            raise ValueError('Clown ID must be an integer.')
        max_id = highest_id()[0]['max']
        if id > max_id or id < 0:
            abort(404)
        with conn.cursor() as cur:
            sql_statement = "SELECT clown_id, clown_name, speciality_name FROM clown JOIN speciality ON clown.speciality_id = speciality.speciality_id WHERE clown_id = %s;"
            cur.execute(sql_statement, str(id))
            data = cur.fetchall()[0]
            score = score_calculator(conn, id)
            if score != 0 or score != None:
                data['avg_score'] = score[0]['score']
            count = number_of_ratings(conn, id)
            if score != 0 or score != None:
                data['number_of_reviews'] = count[0]['count']
            return jsonify(data)


@app.route("/clown/<int:id>/review", methods=["POST"])
def review_clowns_by_id(id) -> Response:
    """User can add a review to a clown."""

    data = request.json
    score = data['score']
    if not isinstance(score, int):
        abort(400)
    if score < 1 or score > 5:
        raise ValueError("Score must be between 1 and 5")
    with conn.cursor() as cur:
        sql_statement = "UPDATE review SET clown_id = %s rating = %s;"
        cur.execute(sql_statement, str(id))
        return jsonify(cur.fetchall())


def highest_id():
    """Finds the highest ID of the clowns"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(clown_id) FROM clown")
        return cur.fetchall()


def score_calculator(connection, id_number):
    """Calculates the score of the clowns"""
    cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT SUM(rating)/COUNT(rating) AS score FROM review LEFT JOIN clown ON review.clown_id = clown.clown_id WHERE clown.clown_id = %s", [id_number])
    rows = cur.fetchall()
    conn.commit()
    cur.close()
    return rows


def number_of_ratings(connection, identification):
    """Counts the number of reviews the clone has."""
    cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT COUNT(rating) AS count FROM review LEFT JOIN clown ON review.clown_id = clown.clown_id WHERE clown.clown_id = %s", [identification])
    rows = cur.fetchall()
    connection.commit()
    cur.close()
    return rows


if __name__ == "__main__":
    app.run(port=8080, debug=True)
