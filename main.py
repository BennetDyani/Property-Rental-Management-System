from src.database import init_database
from src.models import Property, Payment, Maintenance, Tenant

def main():
    init_database()
    print("Database tables created")

if __name__ == "__main__":
    main()