import sqlite3
import os
import psycopg2
import click
from flask import current_app
from flask import g
from flask.cli import with_appcontext
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

def get_db():
    """Connect to the application's configured database. The connection
    is unique for each request and will be reused if this is called
    again.
    """
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False
        )
        g.db.row_factory = sqlite3.Row
        

    return g.db

def pg_db():
    """Get connection to cloud postgres database"""
    # Update connection string information

    host = os.getenv('host')
    dbname = os.getenv('dbname')
    user = os.getenv('user')
    password = os.getenv('password')
    sslmode = os.getenv('sslmode')
    conn_string = "host={0} user={1} dbname={2} password=superflex1! sslmode={4}".format(host, user, dbname, password, sslmode)
    g.db = psycopg2.connect(conn_string)
    # g.db = conn.cursor()
    g.db.autocommit = True
    print("Connection established")

    return g.db


def close_db(e=None):
    """If this request connected to the database, close the
    connection.
    """
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    """Clear existing data and create new tables."""
    # db = get_db()
    db = pg_db()

    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    """Register database functions with the Flask app. This is called by
    the application factory.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
