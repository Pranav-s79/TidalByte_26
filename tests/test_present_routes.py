import json

from flood.present_routes import check, facts, present, template

DOC = {
    "label": "REPLAY · Harvey 2017 estimated peak · not current conditions",
    "depth_limit_m": 0.3, "status": "ok",
    "options": [
        {"id": "A", "kind": "least_deep", "distance_km": 5.74, "unobserved_km": 5.42, "unobserved_share": 0.94,
         "deepest": {"depth_m": 0.16, "source": "Estimated", "road": "South Loop West"}, "n_bridges_not_estimated": 2},
        {"id": "B", "kind": "shortest_within_limit", "distance_km": 5.23, "unobserved_km": 4.47, "unobserved_share": 0.85,
         "deepest": {"depth_m": 0.21, "source": "Estimated", "road": "South Loop West"}, "n_bridges_not_estimated": 3},
    ],
}
GOOD = ("REPLAY: Option A (least-deep) is 5.74 km with its deepest point 0.16 m (Estimated) on South Loop West "
        "and 5.42 km unobserved. Option B (shortest within the limit) is 5.23 km, deepest 0.21 m (Estimated) on "
        "South Loop West, with 4.47 km (85%) unobserved.")


def test_checked_reply_is_shown():
    out = present(DOC, client=lambda m: GOOD)
    assert out["source"] == "nemotron" and out["text"] == GOOD and len(out["attempts"]) == 1


def test_every_number_must_come_from_the_router():
    problems = check(GOOD.replace("5.74", "5.7"), facts(DOC))
    assert problems == ["numbers not in the router output: 5.7"]


def test_banned_words_are_caught_in_any_form():
    for word in ("safe", "Safely", "clear", "clearly", "passable"):
        assert any("banned" in p for p in check(GOOD + f" It is {word}.", facts(DOC))), word
    assert check(GOOD.replace("unobserved.", "unobserved; the rest is unclear."), facts(DOC)) == []


def test_more_than_three_sentences_is_rejected():
    assert check(GOOD + " A is longer. B is shorter.", facts(DOC)) == ["4 sentences; at most 3"]


def test_rejected_reply_is_retried_with_the_problems_listed():
    replies = iter([GOOD.replace("5.23", "5.2"), GOOD])
    seen = []
    out = present(DOC, client=lambda m: seen.append(m) or next(replies))
    assert out["source"] == "nemotron" and len(out["attempts"]) == 2
    assert "5.2" in seen[1][-1]["content"]  # the retry tells the model what it got wrong


def test_two_bad_replies_fall_back_to_the_checked_template():
    out = present(DOC, client=lambda m: "Route A is safe and about 6 km.")
    assert out["source"] == "template" and check(out["text"], facts(DOC)) == []
    assert out["text"].startswith("REPLAY: Option A (least-deep) is 5.74 km")


def test_model_failure_falls_back_to_the_template():
    def down(messages):
        raise RuntimeError("503")
    out = present(DOC, client=down)
    assert out["source"] == "template" and "503" in out["attempts"][0]["problems"][0]


def test_no_route_names_what_blocks_it():
    doc = {"label": "REPLAY · x", "depth_limit_m": 0.1, "status": "no_route_within_limit", "options": [],
           "message": "No route within the depth limit you set.",
           "blocking": [{"osm_id": "123456789", "road": "Braeswood Blvd", "source": "Estimated", "depth_m": 0.42}]}
    text = template(facts(doc))
    assert text == "REPLAY: No route within the depth limit you set. Over the limit on the way through: Braeswood Blvd."
    assert check(text, facts(doc)) == []
    assert "123456789" not in json.dumps(facts(doc))  # OSM ids aren't quotable


def test_template_passes_on_the_real_replay_routes():
    doc = json.load(open("web/data/routes.json"))
    assert check(template(facts(doc)), facts(doc)) == []
