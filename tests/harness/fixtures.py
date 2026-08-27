"""Shared test fixture data for the simulated ADABAS files.

The values mirror the shapes defined in the DDMs (NCCRUISE, NCCONTRACT,
NCCUSTOMER, NCYACHT); CRUISE-STATUS is an A1 field holding the number of
available places, exactly as in the real file.
"""

from .adabas_sim import AdabasSim


def make_db(cruise_status="5"):
    db = AdabasSim()
    db.add_file("NCYACHT", [
        {"YACHT-ID": 4711, "YACHT-NAME": "Sunny Dream", "YACHT-TYPE": "Ketch"},
        {"YACHT-ID": 4712, "YACHT-NAME": "Island Breeze", "YACHT-TYPE": "Sloop"},
    ])
    db.add_file("NCCRUISE", [
        {
            "CRUISE-ID": 196,
            "CRUISE-STATUS": cruise_status,
            "START-DATE": 20260901,
            "END-DATE": 20260908,
            "START-HARBOR": "Agios Nikolaos",
            "DESTINATION-HARBOR": "Santorini",
            "ID-YACHT": 4711,
            "PRICE-1W": 1290.0,
            "PRICE-2W": 2390.0,
            "PRICE-3W": 3290.0,
        },
        {
            "CRUISE-ID": 1484,
            "CRUISE-STATUS": "3",
            "START-DATE": 20261015,
            "END-DATE": 20261029,
            "START-HARBOR": "Paros",
            "DESTINATION-HARBOR": "Lefkas",
            "ID-YACHT": 4712,
            "PRICE-1W": 990.0,
            "PRICE-2W": 1890.0,
            "PRICE-3W": 2690.0,
        },
        {
            "CRUISE-ID": 696,
            "CRUISE-STATUS": "0",  # fully booked
            "START-DATE": 20260920,
            "END-DATE": 20260927,
            "START-HARBOR": "Santorini",
            "DESTINATION-HARBOR": "Paros",
            "ID-YACHT": 4711,
            "PRICE-1W": 1490.0,
            "PRICE-2W": 2790.0,
            "PRICE-3W": 3990.0,
        },
    ])
    db.add_file("NCCUSTOMER", [
        {"PERSON-ID": 10000001, "SURNAME": "Miller", "FIRST-NAME-OLD": "Anna"},
        {"PERSON-ID": 10000002, "SURNAME": "Schmidt", "FIRST-NAME-OLD": "Jens"},
    ])
    db.add_file("NCCONTRACT", [
        {
            "CONTRACT-ID": 500100,
            "PRICE": 990.0,
            "DATE-BOOKING": 20260701,
            "ID-CRUISE": 1484,
            "ID-CUSTOMER": 10000002,
        },
    ])
    return db
