CREATE TABLE IF NOT EXISTS Events (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  content TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  created_by TEXT,
  start_time TIMESTAMPTZ,
  end_time TIMESTAMPTZ,
  description TEXT,
  tracks TEXT[],
  prizes TEXT[]
);

CREATE TABLE IF NOT EXISTS Participants (
  id SERIAL PRIMARY KEY,
  event_id INT REFERENCES Events(id),
  name TEXT NOT NULL,
  email TEXT,
  joined_at TIMESTAMPTZ DEFAULT now()
);
