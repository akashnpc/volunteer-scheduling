"""Goal 4: the shift lifecycle and its rejections."""
from sqlalchemy import text


def sign_up(client, world, shift_id, volunteer, as_user=None):
    """Volunteer signs themselves up; pass as_user=world.coord to act on their behalf."""
    actor = as_user or volunteer
    body = {"volunteer_id": volunteer.id} if as_user else {}
    return client.post(f"/api/shifts/{shift_id}/signups", headers=world.auth(actor), json=body)


def shift_state(client, world, shift_id):
    return client.get(f"/api/shifts/{shift_id}", headers=world.auth(world.coord)).json()["state"]


def test_fill_state_is_derived_from_signup_count(client, world, make_shift):
    shift = make_shift(headcount=2)
    assert shift["state"] == "open"
    first = sign_up(client, world, shift["id"], world.vols[0])
    assert first.status_code == 201
    assert first.json()["state"] == "partially_filled"
    second = sign_up(client, world, shift["id"], world.vols[1])
    assert second.json()["state"] == "filled"
    cancelled = client.delete(
        f"/api/signups/{second.json()['signups'][0]['id']}", headers=world.auth(world.coord)
    )
    assert cancelled.json()["state"] == "partially_filled"


def test_cannot_sign_up_for_filled_shift(client, world, make_shift):
    shift = make_shift(headcount=1)
    assert sign_up(client, world, shift["id"], world.vols[0]).status_code == 201
    r = sign_up(client, world, shift["id"], world.vols[1])
    assert r.status_code == 409
    assert "filled" in r.json()["detail"]


def test_cannot_sign_up_twice(client, world, make_shift):
    shift = make_shift(headcount=3)
    sign_up(client, world, shift["id"], world.vols[0])
    r = sign_up(client, world, shift["id"], world.vols[0])
    assert r.status_code == 409
    assert "already signed up" in r.json()["detail"]


def test_overlapping_shift_is_rejected_even_across_programs(client, world, make_shift):
    other = world.make_program("Tutoring", members=world.vols)
    a = make_shift(day="2026-11-10", start="09:00", minutes=120)
    b = make_shift(day="2026-11-10", start="10:30", minutes=60, program_id=other)
    assert sign_up(client, world, a["id"], world.vols[0]).status_code == 201
    r = sign_up(client, world, b["id"], world.vols[0])
    assert r.status_code == 409
    assert "overlapping" in r.json()["detail"]
    # a different volunteer is unaffected
    assert sign_up(client, world, b["id"], world.vols[1]).status_code == 201


def test_back_to_back_shifts_do_not_overlap(client, world, make_shift):
    a = make_shift(day="2026-11-10", start="09:00", minutes=60)
    b = make_shift(day="2026-11-10", start="10:00", minutes=60)
    assert sign_up(client, world, a["id"], world.vols[0]).status_code == 201
    assert sign_up(client, world, b["id"], world.vols[0]).status_code == 201


def test_cancelling_frees_the_time_window(client, world, make_shift):
    a = make_shift(day="2026-11-10", start="09:00", minutes=120, headcount=1)
    b = make_shift(day="2026-11-10", start="10:00", minutes=120, headcount=1)
    signup = sign_up(client, world, a["id"], world.vols[0]).json()["signups"][0]
    assert sign_up(client, world, b["id"], world.vols[0]).status_code == 409
    client.delete(f"/api/signups/{signup['id']}", headers=world.auth(world.vols[0]))
    assert sign_up(client, world, b["id"], world.vols[0]).status_code == 201


def test_volunteer_must_belong_to_program(client, world, make_shift, session_factory):
    from app.models import ProgramMember

    with session_factory() as db:
        db.delete(db.get(ProgramMember, (world.program_id, world.vols[2].id)))
        db.commit()
    shift = make_shift()
    own = sign_up(client, world, shift["id"], world.vols[2])
    assert own.status_code == 403 and "member" in own.json()["detail"]
    by_coord = sign_up(client, world, shift["id"], world.vols[2], as_user=world.coord)
    assert by_coord.status_code == 409 and "member" in by_coord.json()["detail"]


def test_volunteer_cannot_act_for_someone_else(client, world, make_shift):
    shift = make_shift()
    r = client.post(
        f"/api/shifts/{shift['id']}/signups",
        headers=world.auth(world.vols[0]),
        json={"volunteer_id": world.vols[1].id},
    )
    assert r.status_code == 403
    signup = sign_up(client, world, shift["id"], world.vols[1]).json()["signups"][0]
    r = client.delete(f"/api/signups/{signup['id']}", headers=world.auth(world.vols[0]))
    assert r.status_code == 403
    assert client.delete(f"/api/signups/{signup['id']}", headers=world.auth(world.coord)).status_code == 200


def test_cannot_cancel_twice(client, world, make_shift):
    shift = make_shift()
    signup = sign_up(client, world, shift["id"], world.vols[0]).json()["signups"][0]
    assert client.delete(f"/api/signups/{signup['id']}", headers=world.auth(world.coord)).status_code == 200
    assert client.delete(f"/api/signups/{signup['id']}", headers=world.auth(world.coord)).status_code == 409


def test_close_only_after_scheduled_time_and_then_locks_everything(client, world, make_shift):
    future = make_shift(day="2026-11-10")
    early = client.post(f"/api/shifts/{future['id']}/close", headers=world.auth(world.coord))
    assert early.status_code == 409 and "after its scheduled time" in early.json()["detail"]

    past = make_shift(day="2026-11-02", headcount=3)  # Monday last week relative to NOW
    signup = sign_up(client, world, past["id"], world.vols[0]).json()["signups"][0]
    closed = client.post(f"/api/shifts/{past['id']}/close", headers=world.auth(world.coord))
    assert closed.status_code == 200 and closed.json()["state"] == "closed"

    assert sign_up(client, world, past["id"], world.vols[1]).status_code == 409
    r = client.delete(f"/api/signups/{signup['id']}", headers=world.auth(world.coord))
    assert r.status_code == 409 and "closed" in r.json()["detail"]
    assert client.post(f"/api/shifts/{past['id']}/close", headers=world.auth(world.coord)).status_code == 409
    assert client.patch(
        f"/api/shifts/{past['id']}", headers=world.auth(world.coord), json={"location": "Elsewhere"}
    ).status_code == 409
    assert client.delete(f"/api/shifts/{past['id']}", headers=world.auth(world.coord)).status_code == 409


def test_volunteer_cannot_close_or_edit(client, world, make_shift):
    shift = make_shift(day="2026-11-02")
    v = world.auth(world.vols[0])
    assert client.post(f"/api/shifts/{shift['id']}/close", headers=v).status_code == 403
    assert client.patch(f"/api/shifts/{shift['id']}", headers=v, json={"location": "x"}).status_code == 403
    assert client.delete(f"/api/shifts/{shift['id']}", headers=v).status_code == 403


def test_cannot_lower_headcount_below_signups(client, world, make_shift):
    shift = make_shift(headcount=3)
    for v in world.vols[:2]:
        sign_up(client, world, shift["id"], v)
    r = client.patch(f"/api/shifts/{shift['id']}", headers=world.auth(world.coord), json={"required_headcount": 1})
    assert r.status_code == 409
    ok = client.patch(f"/api/shifts/{shift['id']}", headers=world.auth(world.coord), json={"required_headcount": 2})
    assert ok.status_code == 200 and ok.json()["state"] == "filled"


def test_moving_a_shift_cannot_double_book_a_signed_up_volunteer(client, world, make_shift):
    a = make_shift(day="2026-11-10", start="09:00", minutes=60)
    b = make_shift(day="2026-11-11", start="09:00", minutes=60)
    sign_up(client, world, a["id"], world.vols[0])
    sign_up(client, world, b["id"], world.vols[0])
    r = client.patch(
        f"/api/shifts/{b['id']}", headers=world.auth(world.coord), json={"date": "2026-11-10", "start_time": "09:30"}
    )
    assert r.status_code == 409 and "double-book" in r.json()["detail"]
    same_slot = client.patch(f"/api/shifts/{b['id']}", headers=world.auth(world.coord), json={"date": "2026-11-10"})
    assert same_slot.status_code == 409 and "already starts" in same_slot.json()["detail"]


def test_deleting_a_shift_cancels_signups_and_keeps_history(client, world, make_shift, session_factory):
    shift = make_shift()
    sign_up(client, world, shift["id"], world.vols[0])
    assert client.delete(f"/api/shifts/{shift['id']}", headers=world.auth(world.coord)).status_code == 204
    assert client.get(f"/api/shifts/{shift['id']}", headers=world.auth(world.coord)).status_code == 404
    with session_factory() as db:
        kinds = [r[0] for r in db.execute(text("SELECT event_type FROM shift_events WHERE shift_id=:i ORDER BY id"), {"i": shift["id"]})]
    assert kinds[0] == "created" and "cancellation" in kinds and kinds[-1] == "deleted"
