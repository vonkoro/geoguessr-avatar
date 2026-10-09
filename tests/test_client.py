import httpx

from geoguessr_avatar import GeoGuessrClient


def asset(asset_id: str) -> dict:
    return {
        "id": asset_id,
        "slot": 2,
        "type": "SHIRT",
        "variant": asset_id,
        "meshGlb": "mesh/x.glb",
        "texture": "",
        "icon": "",
        "morphTarget": "",
        "hides": [],
        "rarity": 1,
    }


async def test_get_assets_fetches_in_batches_of_eight(tmp_path):
    requests: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids = request.url.params.get_list("ids")
        requests.append(ids)
        return httpx.Response(200, json=[asset(i) for i in ids[:8]])  # the live API's cap

    ids = [f"SHIRT_{n}" for n in range(19)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        found = await GeoGuessrClient(http=http, cache_dir=tmp_path).get_assets(ids)
    assert [a.id for a in found] == ids
    assert [len(r) for r in requests] == [8, 8, 3]


async def test_get_assets_without_ids_makes_no_request(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await GeoGuessrClient(http=http, cache_dir=tmp_path).get_assets([]) == []
