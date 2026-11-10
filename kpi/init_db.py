from .database import get_session, initialize_database


def main() -> None:
    sessions = get_session()
    session = next(sessions)
    try:
        initialize_database(session)
    finally:
        sessions.close()
    print("KPI database initialized and KPI catalog seeded.")


if __name__ == "__main__":
    main()
