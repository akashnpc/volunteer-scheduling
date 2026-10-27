"""Goals 1, 2, 3 and 5: roles enforced by the server, programs, membership."""


def test_register_login_and_me(client):
    r = client.post("/api/auth/register", json={"name": "New Person", "email": "New@Example.com", "password": "Password1!"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "volunteer"
    assert client.post("/api/auth/register", json={"name": "Dup", "email": "new@example.com", "password": "Password1!"}).status_code == 409
    login = client.post("/api/auth/login", json={"email": "new@example.com", "password": "Password1!"})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["email"] == "new@example.com"
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "wrong-password"}).status_code == 401


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/programs").status_code == 401
    assert client.get("/api/shifts", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_register_cannot_choose_a_role(client):
    r = client.post(
        "/api/auth/register",
        json={"name": "Sneaky", "email": "s@example.com", "password": "Password1!", "role": "coordinator"},
    )
    assert r.json()["user"]["role"] == "volunteer"


def test_volunteer_is_blocked_from_every_coordinator_action(client, world, make_shift):
    v = world.auth(world.vols[0])
    shift = make_shift()
    attempts = [
        client.post("/api/programs", headers=v, json={"name": "X"}),
        client.patch(f"/api/programs/{world.program_id}", headers=v, json={"name": "Y"}),
        client.post(f"/api/programs/{world.program_id}/archive", headers=v),
        client.post(f"/api/programs/{world.program_id}/members", headers=v, json={"user_id": world.vols[1].id}),
        client.delete(f"/api/programs/{world.program_id}/members/{world.vols[1].id}", headers=v),
        client.post("/api/shifts", headers=v, json={
            "program_id": world.program_id, "date": "2026-11-12", "start_time": "09:00",
            "duration_minutes": 60, "location": "x", "required_headcount": 1}),
        client.post(f"/api/shifts/{shift['id']}/notes", headers=v, json={"message": "hi"}),
        client.post(f"/api/alerts/{shift['id']}/dismiss", headers=v),
        client.get(f"/api/programs/{world.program_id}/roster.csv", headers=v),
        client.get("/api/users", headers=v),
        client.post(f"/api/programs/{world.program_id}/schedule", headers=v, json={}),
    ]
    assert [r.status_code for r in attempts] == [403] * len(attempts)


def test_volunteers_only_see_their_programs(client, world, make_shift):
    hidden = world.make_program("Secret Program", members=[world.vols[1]])
    make_shift(program_id=hidden)
    visible = make_shift()
    v0 = world.auth(world.vols[0])
    names = [p["name"] for p in client.get("/api/programs", headers=v0).json()]
    assert names == ["Food Pantry"]
    assert client.get(f"/api/programs/{hidden}", headers=v0).status_code == 404
    shifts = client.get("/api/shifts", headers=v0).json()
    assert [s["id"] for s in shifts["items"]] == [visible["id"]]
    assert client.get("/api/shifts", headers=world.auth(world.coord)).json()["total"] == 2


def test_program_create_edit_archive_restore_keeps_shifts(client, world, make_shift):
    c = world.auth(world.coord)
    created = client.post("/api/programs", headers=c, json={"name": " Trail Cleanup ", "description": "d"})
    assert created.status_code == 201 and created.json()["name"] == "Trail Cleanup"
    pid = created.json()["id"]
    shift = make_shift(program_id=pid)
    assert client.patch(f"/api/programs/{pid}", headers=c, json={"description": "new"}).json()["description"] == "new"

    archived = client.post(f"/api/programs/{pid}/archive", headers=c)
    assert archived.json()["archived"] is True
    assert pid not in [p["id"] for p in client.get("/api/programs", headers=c).json()]
    assert pid in [p["id"] for p in client.get("/api/programs?include_archived=true", headers=c).json()]
    assert shift["id"] not in [s["id"] for s in client.get("/api/shifts", headers=c).json()["items"]]
    # archived programs refuse new shifts, but the data is all still there
    blocked = client.post("/api/shifts", headers=c, json={
        "program_id": pid, "date": "2026-11-20", "start_time": "09:00",
        "duration_minutes": 60, "location": "x", "required_headcount": 1})
    assert blocked.status_code == 409

    restored = client.post(f"/api/programs/{pid}/restore", headers=c)
    assert restored.json()["archived"] is False and restored.json()["shift_count"] == 1
    assert shift["id"] in [s["id"] for s in client.get("/api/shifts", headers=c).json()["items"]]


def test_archived_program_is_hidden_from_its_volunteers(client, world, make_shift):
    make_shift()
    client.post(f"/api/programs/{world.program_id}/archive", headers=world.auth(world.coord))
    v = world.auth(world.vols[0])
    assert client.get("/api/programs", headers=v).json() == []
    assert client.get("/api/shifts", headers=v).json()["total"] == 0


def test_membership_add_remove_and_removal_cancels_signups(client, world, make_shift):
    c = world.auth(world.coord)
    newbie = client.post("/api/users", headers=c, json={"name": "Neo", "email": "neo@example.com", "password": "Password1!"}).json()
    shift = make_shift()
    assert client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(world.vols[0]), json={}).status_code == 201

    dup = client.post(f"/api/programs/{world.program_id}/members", headers=c, json={"user_id": world.vols[0].id})
    assert dup.status_code == 409
    assert client.post(f"/api/programs/{world.program_id}/members", headers=c, json={"user_id": newbie["id"]}).status_code == 201
    assert len(client.get(f"/api/programs/{world.program_id}/members", headers=c).json()) == 4

    assert client.delete(f"/api/programs/{world.program_id}/members/{world.vols[0].id}", headers=c).status_code == 204
    detail = client.get(f"/api/shifts/{shift['id']}", headers=c).json()
    assert detail["signup_count"] == 0 and detail["state"] == "open"
    assert client.get(f"/api/programs/{world.program_id}", headers=world.auth(world.vols[0])).status_code == 404


def test_coordinator_cannot_be_added_as_member(client, world):
    r = client.post(f"/api/programs/{world.program_id}/members", headers=world.auth(world.coord), json={"user_id": world.coord.id})
    assert r.status_code == 404


def test_validation_errors_are_readable(client, world):
    r = client.post("/api/shifts", headers=world.auth(world.coord), json={"program_id": world.program_id})
    assert r.status_code == 422 and "date" in r.json()["detail"]
    bad = client.post("/api/shifts", headers=world.auth(world.coord), json={
        "program_id": world.program_id, "date": "2026-11-12", "start_time": "09:00",
        "duration_minutes": 60, "location": "x", "required_headcount": 0})
    assert bad.status_code == 422
