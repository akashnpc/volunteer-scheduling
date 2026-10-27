"""Goal 9: the history cannot be rewritten."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError


def test_timeline_records_every_step_with_actors(client, world, make_shift):
    c = world.auth(world.coord)
    shift = make_shift(headcount=1)
    v = world.vols[0]
    client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(v), json={})
    client.post(f"/api/shifts/{shift['id']}/notes", headers=c, json={"message": "Gate code is 1234"})
    signup_id = client.get(f"/api/shifts/{shift['id']}", headers=c).json()["signups"][0]["id"]
    client.delete(f"/api/signups/{signup_id}", headers=c)

    events = client.get(f"/api/shifts/{shift['id']}/timeline", headers=c).json()
    kinds = [e["event_type"] for e in events]
    assert kinds == ["created", "signup", "state_change", "note", "cancellation", "state_change"]
    assert events[1]["actor_name"] == v.name and events[1]["volunteer_name"] == v.name
    assert (events[2]["old_state"], events[2]["new_state"]) == ("open", "filled")
    assert events[3]["message"] == "Gate code is 1234" and events[3]["actor_name"] == "Cora Coord"
    assert events[4]["actor_name"] == "Cora Coord" and events[4]["volunteer_name"] == v.name
    assert (events[5]["old_state"], events[5]["new_state"]) == ("filled", "open")


def test_volunteers_can_read_but_not_write_the_timeline(client, world, make_shift):
    shift = make_shift()
    v = world.auth(world.vols[0])
    assert client.get(f"/api/shifts/{shift['id']}/timeline", headers=v).status_code == 200
    assert client.post(f"/api/shifts/{shift['id']}/notes", headers=v, json={"message": "x"}).status_code == 403


def test_no_api_route_edits_or_deletes_events(client, world, make_shift):
    shift = make_shift()
    c = world.auth(world.coord)
    event_id = client.get(f"/api/shifts/{shift['id']}/timeline", headers=c).json()[0]["id"]
    for method in ("put", "patch", "delete"):
        r = getattr(client, method)(f"/api/shifts/{shift['id']}/timeline/{event_id}", headers=c)
        assert r.status_code in (404, 405)


def test_database_itself_refuses_update_and_delete(client, world, make_shift, session_factory):
    shift = make_shift()
    with session_factory() as db:
        with pytest.raises(DatabaseError, match="append-only"):
            db.execute(text("UPDATE shift_events SET message = 'rewritten' WHERE shift_id = :i"), {"i": shift["id"]})
        db.rollback()
        with pytest.raises(DatabaseError, match="append-only"):
            db.execute(text("DELETE FROM shift_events WHERE shift_id = :i"), {"i": shift["id"]})
        db.rollback()
        count = db.execute(text("SELECT COUNT(*) FROM shift_events WHERE shift_id = :i"), {"i": shift["id"]}).scalar()
    assert count == 1
