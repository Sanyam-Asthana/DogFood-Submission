SELECT e.name AS event_name, t.name AS track_name 
FROM events e 
JOIN tracks t ON e.id = t.event_id;