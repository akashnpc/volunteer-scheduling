"""Goal 6: search, filters, sorting and pagination happen in the database."""


def make_many(make_shift):
    pantry = make_shift(day="2026-11-10", start="09:00", location="Community Hall", headcount=1)
    trail = make_shift(day="2026-11-11", start="08:00", location="Ridge Trailhead", headcount=2)
    late = make_shift(day="2026-11-12", start="14:00", location="Community Hall", headcount=3)
    return pantry, trail, late


def ids(response):
    return [s["id"] for s in response.json()["items"]]


def test_text_search_matches_location_and_program_name(client, world, make_shift):
    pantry, trail, late = make_many(make_shift)
    c = world.auth(world.coord)
    assert ids(client.get("/api/shifts?q=ridge", headers=c)) == [trail["id"]]
    assert ids(client.get("/api/shifts?q=hall", headers=c)) == [pantry["id"], late["id"]]
    assert client.get("/api/shifts?q=food", headers=c).json()["total"] == 3  # program name
    assert ids(client.get("/api/shifts?q=hall+14", headers=c)) == []  # every word must match
    assert client.get("/api/shifts?q=%25", headers=c).json()["total"] == 0  # % is literal, not a wildcard


def test_filters_by_program_state_and_date(client, world, make_shift):
    pantry, trail, late = make_many(make_shift)
    other = make_shift(day="2026-11-10", start="18:00", program_id=world.make_program("Tutoring", members=world.vols))
    c = world.auth(world.coord)
    client.post(f"/api/shifts/{pantry['id']}/signups", headers=world.auth(world.vols[0]), json={})
    assert client.get(f"/api/shifts?program_id={other['program_id']}", headers=c).json()["total"] == 1
    assert ids(client.get("/api/shifts?state=filled", headers=c)) == [pantry["id"]]
    assert client.get("/api/shifts?state=open", headers=c).json()["total"] == 3
    assert client.get("/api/shifts?state=bogus", headers=c).status_code == 400
    in_range = client.get("/api/shifts?date_from=2026-11-11&date_to=2026-11-11", headers=c)
    assert ids(in_range) == [trail["id"]]


def test_sorting_by_date_start_time_and_fill_state(client, world, make_shift):
    pantry, trail, late = make_many(make_shift)
    c = world.auth(world.coord)
    assert ids(client.get("/api/shifts?sort=date&order=desc", headers=c)) == [late["id"], trail["id"], pantry["id"]]
    assert ids(client.get("/api/shifts?sort=start_time", headers=c)) == [trail["id"], pantry["id"], late["id"]]
    client.post(f"/api/shifts/{late['id']}/signups", headers=world.auth(world.vols[0]), json={})  # -> partially filled
    client.post(f"/api/shifts/{pantry['id']}/signups", headers=world.auth(world.vols[1]), json={})  # -> filled
    by_state = ids(client.get("/api/shifts?sort=state", headers=c))
    assert by_state == [trail["id"], late["id"], pantry["id"]]  # open, partially filled, filled
    assert client.get("/api/shifts?sort=bogus", headers=c).status_code == 422


def test_pagination_reports_total_matches(client, world, make_shift):
    for day in range(10, 17):
        make_shift(day=f"2026-11-{day}", start="09:00")
    c = world.auth(world.coord)
    first = client.get("/api/shifts?page_size=3&page=1", headers=c).json()
    last = client.get("/api/shifts?page_size=3&page=3", headers=c).json()
    assert (first["total"], first["pages"], len(first["items"])) == (7, 3, 3)
    assert len(last["items"]) == 1 and last["page"] == 3
    assert set(s["id"] for s in first["items"]).isdisjoint(s["id"] for s in last["items"])


def test_mine_filter_and_my_signup_id(client, world, make_shift):
    pantry, trail, _ = make_many(make_shift)
    v = world.auth(world.vols[0])
    client.post(f"/api/shifts/{trail['id']}/signups", headers=v, json={})
    mine = client.get("/api/shifts?mine=true", headers=v).json()
    assert [s["id"] for s in mine["items"]] == [trail["id"]] and mine["items"][0]["my_signup_id"]
    everything = client.get("/api/shifts", headers=v).json()["items"]
    assert {s["id"]: s["my_signup_id"] is not None for s in everything}[pantry["id"]] is False
