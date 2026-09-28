from session import create_session
from config import BASE_URL


def get_talukas(session, district_id):
    """
    Get Talukas for a district.
    For 2026, the portal uses getTalukaName2019.
    """

    url = (
        BASE_URL
        + "/eDisplay/Propertydetails/getTalukaName2019"
    )

    response = session.get(
        url,
        params={
            "district": district_id
        },
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    print("\n========== TALUKAS ==========")
    print("District:", district_id)
    print("Count:", len(data))

    for item in data:
        print(
            item.get("taluka_code"),
            "=>",
            item.get("mtaluka_name")
        )

    return data


def get_villages(session, district_id, taluka_id):
    """
    Get villages for a district + taluka.
    For 2026, the portal uses getVillageName2019.
    """

    url = (
        BASE_URL
        + "/eDisplay/Propertydetails/getVillageName2019"
    )

    response = session.get(
        url,
        params={
            "taluka": taluka_id,
            "district": district_id
        },
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    print("\n========== VILLAGES ==========")
    print("District:", district_id)
    print("Taluka:", taluka_id)
    print("Count:", len(data))

    # The actual API response is a LIST.
    for index, item in enumerate(data):

        print(
            index,
            "=>",
            item.get("am_mareaname")
        )

    return data


if __name__ == "__main__":

    session = create_session()

    # Pune
    district_id = "23"

    # Get Talukas
    talukas = get_talukas(
        session,
        district_id
    )

    # Find Haveli
    haveli = None

    for item in talukas:

        name = item.get(
            "mtaluka_name",
            ""
        ).strip().lower()

        if "हवेली" in name:
            haveli = item
            break

    if not haveli:
        raise RuntimeError(
            "Haveli was not found"
        )

    taluka_id = haveli["taluka_code"]

    print(
        "\nFOUND HAVELI:",
        haveli["mtaluka_name"],
        "=>",
        taluka_id
    )

    # Get villages
    villages = get_villages(
        session,
        district_id,
        taluka_id
    )

    # Find Kharadi
    kharadi = None

    for index, item in enumerate(villages):

        name = item.get(
            "am_mareaname",
            ""
        ).strip().lower()

        if "खराडी" in name:

            kharadi = {
                "index": index,
                "name": item["am_mareaname"]
            }

            break

    if not kharadi:
        raise RuntimeError(
            "Kharadi was not found"
        )

    print(
        "\nFOUND KHARADI:",
        kharadi["name"],
        "=>",
        kharadi["index"]
    )