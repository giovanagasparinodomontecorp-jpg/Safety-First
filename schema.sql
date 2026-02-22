DROP TABLE IF EXISTS occurrence_history;
DROP TABLE IF EXISTS occurrence_images;
DROP TABLE IF EXISTS occurrences;
DROP TABLE IF EXISTS areas;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('usuario', 'responsavel', 'administrador')),
    password TEXT NOT NULL
);

CREATE TABLE areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    manager_user_id INTEGER,
    FOREIGN KEY (manager_user_id) REFERENCES users(id)
);

CREATE TABLE occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL,
    occurrence_type TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('Baixa', 'Média', 'Alta', 'Crítica')),
    status TEXT NOT NULL CHECK (status IN ('Aberto', 'Em atendimento', 'Aguardando terceiros', 'Resolvido', 'Cancelado')),
    requester_id INTEGER NOT NULL,
    responsible_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    FOREIGN KEY (area_id) REFERENCES areas(id),
    FOREIGN KEY (requester_id) REFERENCES users(id),
    FOREIGN KEY (responsible_id) REFERENCES users(id)
);

CREATE TABLE occurrence_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurrence_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    FOREIGN KEY (occurrence_id) REFERENCES occurrences(id)
);

CREATE TABLE occurrence_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurrence_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    comment TEXT,
    changed_at TEXT NOT NULL,
    FOREIGN KEY (occurrence_id) REFERENCES occurrences(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
