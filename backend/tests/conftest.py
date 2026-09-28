import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
import uuid
from app.core.config import settings
from app.models.location import State, District, Taluka, Village

# 2. Add TEST_DATABASE_URL validation
def get_test_db_url():
    test_url = str(getattr(settings, "TEST_DATABASE_URL", ""))
    main_url = str(settings.DATABASE_URL)
    
    if not test_url:
        raise ValueError("TEST_DATABASE_URL is not configured.")
        
    if test_url == main_url:
        raise ValueError("TEST_DATABASE_URL matches DATABASE_URL! Refusing to run tests against the main database.")
        
    if "esearch_igr_test" not in test_url:
        raise ValueError(f"TEST_DATABASE_URL does not contain 'esearch_igr_test'. Found: {test_url}")
        
    return test_url

TEST_DATABASE_URL = get_test_db_url()

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Apply Alembic migrations to the test database.
    """
    alembic_cfg = Config("alembic.ini")
    # Override sqlalchemy.url in alembic config to point to the test db
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    
    # Run migrations to head
    command.upgrade(alembic_cfg, "head")
    
    db = TestingSessionLocal()
    try:
        st = db.query(State).filter_by(source_id="27").first()
        if not st:
            st = State(id=uuid.uuid4(), source_system="IGR_MAHARASHTRA", source_id="27", name_en="Maharashtra")
            db.add(st)
            
        d = db.query(District).filter_by(source_id="23").first()
        if not d:
            d = District(id=uuid.uuid4(), state_id=st.id, source_system="IGR_MAHARASHTRA", source_id="23", name_en="पुणे")
            db.add(d)
        elif d.name_en != "पुणे":
            d.name_en = "पुणे"
            db.commit()
            
        t = db.query(Taluka).filter_by(source_id="1", district_id=d.id).first()
        if not t:
            t = Taluka(id=uuid.uuid4(), district_id=d.id, source_system="IGR_MAHARASHTRA", source_id="1", name_en="हवेली")
            db.add(t)
        elif t.name_en != "हवेली":
            t.name_en = "हवेली"
            db.commit()
            
        v = db.query(Village).filter_by(source_id="43", taluka_id=t.id).first()
        if not v:
            v = Village(id=uuid.uuid4(), taluka_id=t.id, source_system="IGR_MAHARASHTRA", source_id="43", name_en="खराडी (पुणे महापालिकेमध्ये समाविष्ट)")
            db.add(v)
            db.commit()
    finally:
        db.close()
    
    yield

@pytest.fixture(scope="module")
def db():
    """
    Module-level database session fixture.
    """
    session = TestingSessionLocal()
    yield session
    session.close()

# FastAPI override fixture
@pytest.fixture(scope="module", autouse=True)
def override_get_db():
    """
    Override FastAPI get_db dependency to use the test database.
    """
    from app.api.dependencies import get_db
    from app.main import app

    def override_get_db_session():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db_session
    yield
    app.dependency_overrides.clear()
