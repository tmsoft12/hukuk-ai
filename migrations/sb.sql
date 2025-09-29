-- Active: 1756227276542@@127.0.0.1@5432@ragdb
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    owner_id INT REFERENCES users(id)
);




SELECT title, embedding FROM documents LIMIT 5;
