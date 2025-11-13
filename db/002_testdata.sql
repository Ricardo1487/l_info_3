INSERT INTO users (username, email, password_hash, role)
VALUES
  ('admin', 'admin@example.com', 'dummyhash', 'ADMIN'),
  ('hiwi', 'hiwi@example.com', 'dummyhash', 'HIWI');

INSERT INTO boxes (box_code, description)
VALUES
  ('BOX-001', 'Arduino Starterkit'),
  ('BOX-002', 'Raspberry Pi Set');

INSERT INTO loans (
  box_id, contact_email, status,
  planned_start_date, planned_end_date,
  created_by_user_id
)
VALUES
  (1, 'student1@th-koeln.de', 'OPEN', '2025-11-10', '2025-11-17', 2),
  (2, 'student2@th-koeln.de', 'OVERDUE', '2025-11-01', '2025-11-08', 2);