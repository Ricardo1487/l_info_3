CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('ADMIN', 'HIWI') NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE boxes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  box_code VARCHAR(50) UNIQUE,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE loans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  box_id INT NOT NULL,
  contact_email VARCHAR(100) NOT NULL,
  status ENUM('OPEN','RETURNED','OVERDUE','MISSING_ITEMS') NOT NULL,
  planned_start_date DATE NOT NULL,
  planned_end_date DATE NOT NULL,
  actual_start_date DATE,
  actual_end_date DATE,
  created_by_user_id INT,
  closed_by_user_id INT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_loans_box
    FOREIGN KEY (box_id) REFERENCES boxes(id),
  CONSTRAINT fk_loans_created_by
    FOREIGN KEY (created_by_user_id) REFERENCES users(id),
  CONSTRAINT fk_loans_closed_by
    FOREIGN KEY (closed_by_user_id) REFERENCES users(id)
);

CREATE TABLE photos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  loan_id INT NOT NULL,
  type ENUM('INITIAL','RETURN') NOT NULL,
  file_path TEXT NOT NULL,
  taken_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by_user_id INT,

  CONSTRAINT fk_photos_loan
    FOREIGN KEY (loan_id) REFERENCES loans(id),
  CONSTRAINT fk_photos_created_by
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE TABLE detected_objects (
  id INT AUTO_INCREMENT PRIMARY KEY,
  photo_id INT NOT NULL,
  label VARCHAR(100) NOT NULL,
  confidence DECIMAL(4,3),
  quantity INT,
  is_manually_edited BOOLEAN NOT NULL DEFAULT FALSE,

  CONSTRAINT fk_detected_objects_photo
    FOREIGN KEY (photo_id) REFERENCES photos(id)
);

CREATE TABLE reminders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  loan_id INT NOT NULL,
  reminder_type ENUM('DUE_SOON','OVERDUE') NOT NULL,
  scheduled_at DATETIME NOT NULL,
  sent_at DATETIME,

  CONSTRAINT fk_reminders_loan
    FOREIGN KEY (loan_id) REFERENCES loans(id)
);