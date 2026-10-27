"""Goal 7: recurring schedule generation and the roster CSV."""
import csv
import io


def generate(client, world, **overrides):
    body = {
        "start_date": "2026-11-09", "end_date": "2026-11-30", "day_of_week": 1,  # Tuesdays
        "start_time": "09:00", "duration_minutes": 180, "location": "Community Hall",
        "required_headcount": 4, "excluded_dates": [],
    }
    body.update(overrides)
    return client.post(f"/api/programs/{world.program_id}/schedule", headers=world.auth(world.coord), json=body)


def test_creates_one_shift_per_week_on_the_chosen_weekday(client, world):
    r = generate(client, world)
    assert r.status_code == 201
    created = r.json()["created"]
    assert [s["date"] for s in created] == ["2026-11-10", "2026-11-17", "2026-11-24"]
    assert all(s["state"] == "open" and s["required_headcount"] == 4 for s in created)
    assert r.json()["skipped"] == []


def test_reports_holidays_and_existing_shifts_as_skipped(client, world, make_shift):
    make_shift(day="2026-11-17", start="09:00")  # already there at that date+time
    make_shift(day="2026-11-24", start="13:00")  # same date, different time: does not clash
    r = generate(client, world, excluded_dates=["2026-11-10", "2026-11-12"])  # the 12th is not a Tuesday
    body = r.json()
    assert [s["date"] for s in body["created"]] == ["2026-11-24"]
    assert body["skipped"] == [
        {"date": "2026-11-10", "reason": "excluded_holiday"},
        {"date": "2026-11-17", "reason": "already_exists"},
    ]


def test_running_the_same_schedule_twice_creates_nothing_new(client, world):
    generate(client, world)
    again = generate(client, world).json()
    assert again["created"] == []
    assert [s["reason"] for s in again["skipped"]] == ["already_exists"] * 3


def test_generated_shifts_have_history(client, world):
    shift_id = generate(client, world).json()["created"][0]["id"]
    events = client.get(f"/api/shifts/{shift_id}/timeline", headers=world.auth(world.coord)).json()
    assert [e["event_type"] for e in events] == ["created"]


def test_schedule_input_validation(client, world):
    assert generate(client, world, end_date="2026-11-01").status_code == 400
    assert generate(client, world, end_date="2028-12-31").status_code == 400
    assert generate(client, world, day_of_week=9).status_code == 422
    client.post(f"/api/programs/{world.program_id}/archive", headers=world.auth(world.coord))
    assert generate(client, world).status_code == 409


def test_roster_lists_every_volunteer_with_total_hours(client, world, make_shift):
    a = make_shift(day="2026-11-10", start="09:00", minutes=90)
    b = make_shift(day="2026-11-11", start="09:00", minutes=150)
    c = make_shift(day="2026-11-12", start="09:00", minutes=60)
    v1, v2, _ = world.vols
    for shift, vol in ((a, v1), (b, v1), (c, v2)):
        client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(vol), json={})
    cancelled = client.post(f"/api/shifts/{c['id']}/signups", headers=world.auth(world.vols[2]), json={}).json()
    client.delete(f"/api/signups/{cancelled['signups'][0]['id']}", headers=world.auth(world.vols[2]))

    r = client.get(f"/api/programs/{world.program_id}/roster.csv", headers=world.auth(world.coord))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    by_email = {row["email"]: row for row in rows}
    assert len(rows) == 3  # includes the volunteer with no signups
    assert (by_email["vol1@example.com"]["shifts_signed_up"], by_email["vol1@example.com"]["total_hours"]) == ("2", "4.00")
    assert by_email["vol2@example.com"]["total_hours"] == "1.00"
    assert by_email["vol3@example.com"]["total_hours"] == "0.00"  # cancelled signups do not count


def test_roster_neutralises_spreadsheet_formulas(client, world, session_factory):
    from app.models import User

    with session_factory() as db:
        db.get(User, world.vols[0].id).name = "=HYPERLINK(\"http://evil\")"
        db.commit()
    r = client.get(f"/api/programs/{world.program_id}/roster.csv", headers=world.auth(world.coord))
    assert "'=HYPERLINK" in r.text
