-- USERS
CREATE TABLE users (
  id            SERIAL PRIMARY KEY,
  username      VARCHAR(50) UNIQUE NOT NULL,
  email         VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(10) NOT NULL CHECK (role IN ('ADMIN', 'HIWI')),
  created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- BOXES
CREATE TABLE boxes (
  id          SERIAL PRIMARY KEY,
  box_code    VARCHAR(50) UNIQUE,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

-- LOANS
CREATE TABLE loans (
  id                  SERIAL PRIMARY KEY,
  box_id              INTEGER NOT NULL,
  contact_email       VARCHAR(100) NOT NULL,
  status              VARCHAR(20) NOT NULL CHECK (status IN ('OPEN','RETURNED','OVERDUE','MISSING_ITEMS')),
  planned_start_date  DATE NOT NULL,
  planned_end_date    DATE NOT NULL,
  actual_end_date     DATE,
  created_by_user_id  INTEGER,
  closed_by_user_id   INTEGER,
  created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
  
  CONSTRAINT fk_loans_box
    FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE RESTRICT,
  CONSTRAINT fk_loans_created_by
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_loans_closed_by
    FOREIGN KEY (closed_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
  
  -- fachliche Constraints
  CONSTRAINT chk_planned_dates
    CHECK (planned_end_date >= planned_start_date),
  CONSTRAINT chk_actual_dates
    CHECK (
      OR actual_end_date IS NULL
      OR actual_end_date >= actual_start_date
    )
);

-- PHOTOS
CREATE TABLE photos (
  id                 SERIAL PRIMARY KEY,
  loan_id            INTEGER NOT NULL,
  type               VARCHAR(10) NOT NULL CHECK (type IN ('INITIAL','RETURN')),
  file_path          TEXT NOT NULL,
  taken_at           TIMESTAMP NOT NULL DEFAULT NOW(),
  created_by_user_id INTEGER,
  
  CONSTRAINT fk_photos_loan
    FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE,
  CONSTRAINT fk_photos_created_by
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- DETECTED OBJECTS
CREATE TABLE detected_objects (
  id                 SERIAL PRIMARY KEY,
  photo_id           INTEGER NOT NULL,
  label              VARCHAR(100) NOT NULL,
  confidence         NUMERIC(4,3),
  quantity           INTEGER,
  is_manually_edited BOOLEAN NOT NULL DEFAULT FALSE,
  
  CONSTRAINT fk_detected_objects_photo
    FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
);

-- REMINDERS
CREATE TABLE reminders (
  id            SERIAL PRIMARY KEY,
  loan_id       INTEGER NOT NULL,
  reminder_type VARCHAR(20) NOT NULL CHECK (reminder_type IN ('DUE_SOON','OVERDUE')),
  scheduled_at  TIMESTAMP NOT NULL,
  sent_at       TIMESTAMP,
  
  CONSTRAINT fk_reminders_loan
    FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE
);
