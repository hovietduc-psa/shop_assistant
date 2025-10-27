#!/usr/bin/env python3
"""
Script to run only the database service and test connectivity
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class DatabaseRunner:
    """Manages database service only"""

    def __init__(self):
        self.db_process = None

    def log(self, message, status='info'):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_icon = {
            'pass': '✅',
            'fail': '❌',
            'warn': '⚠️',
            'info': 'ℹ️',
            'start': '🚀',
            'stop': '🛑'
        }.get(status, '🔍')
        print(f"{status_icon} [{timestamp}] {message}")

    def check_docker(self):
        """Check if Docker is available"""
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.log("Docker is available")
                return True
            else:
                self.log("Docker is not available", 'fail')
                return False
        except FileNotFoundError:
            self.log("Docker command not found", 'fail')
            return False

    def check_postgres_local(self):
        """Check if PostgreSQL is already running locally"""
        try:
            import psycopg2
            conn = psycopg2.connect("postgresql://postgres:password@localhost:5432/shop_assistant")
            conn.close()
            self.log("PostgreSQL is already running locally")
            return True
        except Exception as e:
            self.log(f"PostgreSQL not running locally: {e}")
            return False

    def start_docker_db(self):
        """Start only PostgreSQL Docker service"""
        self.log("Starting PostgreSQL Docker service...", 'start')

        # Create a docker-compose file for just the database
        docker_compose_content = '''version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: shop_assistant_db
    environment:
      - POSTGRES_DB=shop_assistant
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - shop-assistant-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:

networks:
  shop-assistant-network:
    driver: bridge
'''

        # Write docker-compose file
        compose_file = project_root / 'docker-compose.db.yml'
        with open(compose_file, 'w') as f:
            f.write(docker_compose_content)

        self.log("Created docker-compose.db.yml")

        # Start only the database service
        try:
            cmd = ['docker-compose', '-f', 'docker-compose.db.yml', 'up', '-d', 'db']
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)

            if result.returncode == 0:
                self.log("PostgreSQL Docker service started successfully")
                return True
            else:
                self.log(f"Failed to start PostgreSQL: {result.stderr}", 'fail')
                return False
        except Exception as e:
            self.log(f"Error starting PostgreSQL: {e}", 'fail')
            return False

    def wait_for_db(self, timeout=60):
        """Wait for database to be ready"""
        self.log("Waiting for PostgreSQL to be ready...")

        for i in range(timeout):
            try:
                import psycopg2
                conn = psycopg2.connect("postgresql://postgres:password@localhost:5432/shop_assistant")
                conn.close()
                self.log(f"PostgreSQL is ready (took {i+1} seconds)")
                return True
            except Exception:
                time.sleep(1)
                if i % 10 == 0:
                    self.log(f"Waiting for database... ({i+1}/{timeout}s)")

        self.log("PostgreSQL failed to start within timeout", 'fail')
        return False

    def setup_database(self):
        """Setup database tables"""
        self.log("Setting up database tables...")

        try:
            # Run migrations
            result = subprocess.run(['alembic', 'upgrade', 'head'],
                                    cwd=project_root,
                                    capture_output=True,
                                    text=True)

            if result.returncode == 0:
                self.log("Database migrations completed successfully")
                return True
            else:
                self.log(f"Database migrations failed: {result.stderr}", 'fail')
                # Try to see if alembic exists
                try:
                    subprocess.run(['alembic', 'current'], cwd=project_root, capture_output=True)
                    self.log("Alembic is available but migrations failed", 'warn')
                except FileNotFoundError:
                    self.log("Alembic not found - database tables may need manual setup", 'warn')
                return False
        except Exception as e:
            self.log(f"Error running migrations: {e}", 'fail')
            return False

    def test_db_connection(self):
        """Test database connection and basic operations"""
        self.log("Testing database connection...")

        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            # Test basic connection
            conn = psycopg2.connect("postgresql://postgres:password@localhost:5432/shop_assistant",
                                    cursor_factory=RealDictCursor)
            cursor = conn.cursor()

            # Test basic query
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            self.log(f"PostgreSQL version: {version[0]}", 'pass')

            # Test if we can create tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Test insert
            cursor.execute("""
                INSERT INTO test_table (message) VALUES (%s)
                RETURNING id;
            """, ("Database connection test at " + datetime.now().isoformat(),))

            result = cursor.fetchone()
            self.log(f"Test insert successful: ID {result[0]}", 'pass')

            # Test select
            cursor.execute("SELECT COUNT(*) FROM test_table;")
            count = cursor.fetchone()
            self.log(f"Test select successful: {count[0]} records", 'pass')

            # Clean up
            cursor.execute("DROP TABLE IF EXISTS test_table;")
            conn.commit()

            cursor.close()
            conn.close()

            self.log("Database connection test completed successfully", 'pass')
            return True

        except Exception as e:
            self.log(f"Database connection test failed: {e}", 'fail')
            return False

    def create_sample_data(self):
        """Create some sample data for testing"""
        self.log("Creating sample data...")

        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect("postgresql://postgres:password@localhost:5432/shop_assistant",
                                    cursor_factory=RealDictCursor)
            cursor = conn.cursor()

            # Create a simple test table to verify database is working
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS connection_test (
                    id SERIAL PRIMARY KEY,
                    test_name VARCHAR(100),
                    test_result VARCHAR(20),
                    test_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Insert test data
            cursor.execute("""
                INSERT INTO connection_test (test_name, test_result) VALUES
                (%s, %s)
                ON CONFLICT (test_name) DO UPDATE SET
                test_result = EXCLUDED.test_result,
                test_timestamp = CURRENT_TIMESTAMP;
            """, ("database_connection_test", "SUCCESS"))

            # Verify data
            cursor.execute("SELECT * FROM connection_test WHERE test_name = %s;", ("database_connection_test",))
            result = cursor.fetchone()

            if result and result['test_result'] == 'SUCCESS':
                self.log("Sample data created successfully", 'pass')
            else:
                self.log("Sample data creation failed", 'fail')

            conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            self.log(f"Error creating sample data: {e}", 'fail')
            return False

    def stop_database(self):
        """Stop the database service"""
        self.log("Stopping PostgreSQL service...", 'stop')

        try:
            result = subprocess.run(['docker-compose', '-f', 'docker-compose.db.yml', 'down'],
                                    cwd=project_root, capture_output=True, text=True)

            if result.returncode == 0:
                self.log("PostgreSQL service stopped")
                return True
            else:
                self.log(f"Error stopping PostgreSQL: {result.stderr}", 'warn')
                return False
        except Exception as e:
            self.log(f"Error stopping database: {e}", 'warn')
            return False

    def get_connection_info(self):
        """Get database connection information"""
        info = {
            "host": "localhost",
            "port": 5432,
            "database": "shop_assistant",
            "user": "postgres",
            "password": "password",
            "connection_string": "postgresql://postgres:password@localhost:5432/shop_assistant"
        }

        print(f"\n📊 Database Connection Information:")
        print(f"=" * 40)
        print(f"Host: {info['host']}")
        print(f"Port: {info['port']}")
        print(f"Database: {info['database']}")
        print(f"User: {info['user']}")
        print(f"Password: {info['password']}")
        print(f"Connection String: {info['connection_string']}")

        # Test if database is running
        try:
            import psycopg2
            conn = psycopg2.connect(info["connection_string"])
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"✅ Database is running: {version[0][:50]}...")
            conn.close()
        except Exception as e:
            print(f"❌ Database is not running: {e}")

        return info


def main():
    """Main function"""
    print("🗄️ Shop Assistant AI - Database Runner")
    print("=" * 50)

    db_runner = DatabaseRunner()

    try:
        # Handle command line arguments
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()

            if command == 'stop':
                db_runner.stop_database()
                return
            elif command == 'test':
                # Just test connection if database is already running
                if db_runner.check_postgres_local():
                    db_runner.test_db_connection()
                else:
                    print("❌ Database is not running. Start it first with 'python scripts/run_db_only.py'")
                return
            elif command == 'info':
                db_runner.get_connection_info()
                return

        # Step 1: Check prerequisites
        print("\n🔍 Step 1: Checking prerequisites...")
        if not db_runner.check_docker():
            print("❌ Docker is required. Please install Docker first.")
            return

        # Step 2: Check if database is already running
        print("\n🔍 Step 2: Checking if PostgreSQL is already running...")
        if db_runner.check_postgres_local():
            print("✅ PostgreSQL is already running!")
        else:
            # Step 3: Start database
            print("\n🚀 Step 3: Starting PostgreSQL...")
            if not db_runner.start_docker_db():
                print("❌ Failed to start PostgreSQL")
                return

            # Step 4: Wait for database to be ready
            print("\n⏳ Step 4: Waiting for PostgreSQL to be ready...")
            if not db_runner.wait_for_db():
                print("❌ PostgreSQL failed to start properly")
                return

        # Step 5: Setup database
        print("\n🗄️ Step 5: Setting up database...")
        if not db_runner.setup_database():
            print("⚠️ Database setup had issues, but continuing...")

        # Step 6: Test database connection
        print("\n🧪 Step 6: Testing database connection...")
        if not db_runner.test_db_connection():
            print("❌ Database connection test failed")
            return

        # Step 7: Create sample data
        print("\n📝 Step 7: Creating sample data...")
        db_runner.create_sample_data()

        # Step 8: Display connection info
        print("\n📊 Step 8: Connection information:")
        connection_info = db_runner.get_connection_info()

        print("\n" + "=" * 50)
        print("🎉 PostgreSQL is ready for use!")
        print("=" * 50)
        print(f"   Connection String: {connection_info['connection_string']}")
        print(f"   You can now connect using: psql {connection_info['connection_string']}")
        print("\n💡 To stop the database later, run: python scripts/run_db_only.py stop")
        print("💡 To test connection later, run: python scripts/run_db_only.py test")

    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()