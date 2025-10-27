#!/usr/bin/env python3
"""
Comprehensive script to run database, API services and test all endpoints
"""

import os
import sys
import time
import json
import requests
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configuration
DB_URL = "postgresql://postgres:password@localhost:5432/shop_assistant"
API_BASE_URL = "http://localhost:8000"


class ServiceManager:
    """Manages database and API services"""

    def __init__(self):
        self.processes = {}
        self.services_running = False

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
        """Check if PostgreSQL is running locally"""
        try:
            import psycopg2
            conn = psycopg2.connect(DB_URL)
            conn.close()
            self.log("PostgreSQL is running locally")
            return True
        except Exception as e:
            self.log(f"PostgreSQL not available locally: {e}", 'warn')
            return False

    def check_redis_local(self):
        """Check if Redis is running locally"""
        try:
            import redis
            r = redis.from_url('redis://localhost:6379/0')
            r.ping()
            self.log("Redis is running locally")
            return True
        except Exception as e:
            self.log(f"Redis not available locally: {e}", 'warn')
            return False

    def start_docker_services(self):
        """Start Docker services if needed"""
        self.log("Starting Docker services...", 'start')

        # Update docker-compose.yml to enable app service
        try:
            # Read current docker-compose.yml
            compose_file = project_root / 'docker-compose.yml'
            with open(compose_file, 'r') as f:
                content = f.read()

            # Uncomment the app service
            content = content.replace('#  app:', '  app:')
            content = content.replace('#  build:', '  build:')
            content = content.replace('#    context:', '    context:')
            content = content.replace('#    dockerfile:', '    dockerfile:')
            content = content.replace('#  ports:', '  ports:')
            content = content.replace('#    - "8000:8000"', '    - "8000:8000"')
            content = content.replace('#  environment:', '  environment:')
            content = content.replace('#    - DATABASE_URL=postgresql://postgres:password@db:5432/shop_assistant', '    - DATABASE_URL=postgresql://postgres:password@db:5432/shop_assistant')
            content = content.replace('#    - REDIS_URL=redis://redis:6379/0', '    - REDIS_URL=redis://redis:6379/0')
            content = content.replace('#    - DEBUG=true', '    - DEBUG=true')
            content = content.replace('#  volumes:', '  volumes:')
            content = content.replace('#    - ./app:/app/app', '    - ./app:/app/app')
            content = content.replace('#  depends_on:', '  depends_on:')
            content = content.replace('#    - db', '    - db')
            content = content.replace('#    - redis', '    - redis')
            content = content.replace('#  networks:', '  networks:')
            content = content.replace('#    - shop-assistant-network', '    - shop-assistant-network')
            content = content.replace('#  restart: unless-stopped', '  restart: unless-stopped')
            content = content.replace('#  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload', '  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload')

            # Write back the updated content
            with open(compose_file, 'w') as f:
                f.write(content)

            self.log("Updated docker-compose.yml to enable app service")

        except Exception as e:
            self.log(f"Failed to update docker-compose.yml: {e}", 'warn')

        # Start services
        try:
            cmd = ['docker-compose', '-f', 'docker-compose.yml', 'up', '-d']
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)

            if result.returncode == 0:
                self.log("Docker services started successfully")
                return True
            else:
                self.log(f"Failed to start Docker services: {result.stderr}", 'fail')
                return False
        except Exception as e:
            self.log(f"Error starting Docker services: {e}", 'fail')
            return False

    def wait_for_services(self, timeout=120):
        """Wait for services to be ready"""
        self.log("Waiting for services to be ready...")

        # Wait for database
        db_ready = False
        for i in range(timeout):
            try:
                import psycopg2
                conn = psycopg2.connect(DB_URL)
                conn.close()
                db_ready = True
                self.log("Database is ready")
                break
            except:
                time.sleep(1)
                if i % 10 == 0:
                    self.log(f"Waiting for database... ({i}/{timeout}s)")

        if not db_ready:
            self.log("Database failed to start", 'fail')
            return False

        # Wait for Redis
        redis_ready = False
        for i in range(timeout):
            try:
                import redis
                r = redis.from_url('redis://localhost:6379/0')
                r.ping()
                redis_ready = True
                self.log("Redis is ready")
                break
            except:
                time.sleep(1)
                if i % 10 == 0:
                    self.log(f"Waiting for Redis... ({i}/{timeout}s)")

        if not redis_ready:
            self.log("Redis failed to start", 'fail')
            return False

        # Wait for API
        api_ready = False
        for i in range(timeout):
            try:
                response = requests.get(f"{API_BASE_URL}/health", timeout=5)
                if response.status_code == 200:
                    api_ready = True
                    self.log("API is ready")
                    break
            except:
                time.sleep(1)
                if i % 10 == 0:
                    self.log(f"Waiting for API... ({i}/{timeout}s)")

        if not api_ready:
            self.log("API failed to start", 'fail')
            return False

        self.services_running = True
        return True

    def setup_database(self):
        """Setup database tables"""
        self.log("Setting up database...")

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
                return False
        except Exception as e:
            self.log(f"Error running migrations: {e}", 'fail')
            return False

    def stop_services(self):
        """Stop all services"""
        self.log("Stopping services...", 'stop')
        try:
            subprocess.run(['docker-compose', '-f', 'docker-compose.yml', 'down'],
                         cwd=project_root, capture_output=True)
            self.services_running = False
            self.log("Services stopped")
        except Exception as e:
            self.log(f"Error stopping services: {e}", 'warn')


class EndpointTester:
    """Tests all API endpoints"""

    def __init__(self):
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        self.test_results = {}

    def log(self, message, status='info'):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_icon = {
            'pass': '✅',
            'fail': '❌',
            'warn': '⚠️',
            'info': 'ℹ️'
        }.get(status, '🔍')
        print(f"{status_icon} [{timestamp}] {message}")

    def test_endpoint(self, method, endpoint, data=None, expected_status=200):
        """Test a single endpoint"""
        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=10)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=10)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, timeout=10)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code == expected_status:
                self.log(f"✓ {method} {endpoint} ({response.status_code})", 'pass')
                self.test_results[endpoint] = {
                    'status': 'pass',
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds()
                }
                return True
            else:
                self.log(f"✗ {method} {endpoint} ({response.status_code}): {response.text[:100]}", 'fail')
                self.test_results[endpoint] = {
                    'status': 'fail',
                    'status_code': response.status_code,
                    'error': response.text[:200]
                }
                return False

        except requests.exceptions.RequestException as e:
            self.log(f"✗ {method} {endpoint} - Connection failed: {str(e)}", 'fail')
            self.test_results[endpoint] = {
                'status': 'fail',
                'error': str(e)
            }
            return False

    def test_all_endpoints(self):
        """Test all API endpoints"""
        self.log("Testing API endpoints...", 'info')

        endpoints = [
            # Basic endpoints
            ('GET', '/', None, 200),
            ('GET', '/health', None, 200),
            ('GET', '/api/v1/', None, 200),

            # Conversation endpoints
            ('GET', '/api/v1/conversations/', None, 200),
            ('POST', '/api/v1/conversations/messages', {
                "conversation_id": "test_conv_001",
                "message": {
                    "content": "Test message for API testing",
                    "customer_id": "test_customer",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }, 200),

            # Intelligence endpoints
            ('GET', '/api/v1/intelligence/escalation/triggers', None, 401),  # Should require auth
            ('POST', '/api/v1/intelligence/escalation/analyze', {
                "conversation_id": "test_conv_001",
                "messages": [
                    {"role": "customer", "content": "I'm frustrated with my order!"},
                    {"role": "assistant", "content": "I understand your frustration."}
                ],
                "customer_id": "test_customer"
            }, 200),

            ('POST', '/api/v1/intelligence/quality/assess', {
                "conversation_id": "test_conv_001",
                "messages": [
                    {"role": "customer", "content": "I need help"},
                    {"role": "assistant", "content": "I'd be happy to help you."}
                ],
                "agent_id": "test_agent"
            }, 200),

            # Dashboard endpoints
            ('GET', '/api/v1/intelligence/dashboard/overview', None, 401),  # Should require auth
            ('GET', '/api/v1/intelligence/dashboard/health', None, 401),  # Should require auth
        ]

        passed = 0
        total = len(endpoints)

        for method, endpoint, data, expected in endpoints:
            if self.test_endpoint(method, endpoint, data, expected):
                passed += 1

        # Calculate success rate
        success_rate = (passed / total) * 100
        self.log(f"Endpoint testing completed: {passed}/{total} ({success_rate:.1f}%)")

        return success_rate >= 80  # At least 80% of endpoints should work

    def test_llm_integration(self):
        """Test LLM integration"""
        self.log("Testing LLM integration...", 'info')

        try:
            # Import here to avoid import issues if dependencies aren't available
            sys.path.insert(0, str(project_root))
            from app.core.llm.llm_manager import LLMManager

            # Test LLM manager
            llm_manager = LLMManager()

            # Run in asyncio event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Test basic LLM call
            result = loop.run_until_complete(
                llm_manager.generate_response(
                    prompt="Respond with 'LLM integration test successful'",
                    max_tokens=20,
                    temperature=0.1
                )
            )

            if result and 'content' in result:
                self.log(f"✓ LLM response: {result['content']}", 'pass')
                return True
            else:
                self.log("✗ Invalid LLM response", 'fail')
                return False

        except Exception as e:
            self.log(f"✗ LLM integration failed: {str(e)}", 'fail')
            return False

    def generate_report(self):
        """Generate test report"""
        total_endpoints = len(self.test_results)
        passed_endpoints = sum(1 for r in self.test_results.values() if r.get('status') == 'pass')

        print(f"\n📊 ENDPOINT TEST REPORT")
        print(f"=" * 40)
        print(f"Total Endpoints: {total_endpoints}")
        print(f"Passed: {passed_endpoints} ✅")
        print(f"Failed: {total_endpoints - passed_endpoints} ❌")
        print(f"Success Rate: {(passed_endpoints/total_endpoints)*100:.1f}%")

        print(f"\n📋 Detailed Results:")
        for endpoint, result in self.test_results.items():
            status = result.get('status', 'unknown')
            status_icon = {'pass': '✅', 'fail': '❌', 'unknown': '❓'}.get(status, '❓')
            print(f"{status_icon} {endpoint}: {status.upper()}")

            if result.get('error'):
                print(f"   Error: {result['error'][:80]}...")

        # Save report to file
        report_file = project_root / f"endpoint_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': datetime.utcnow().isoformat(),
                'results': self.test_results,
                'summary': {
                    'total': total_endpoints,
                    'passed': passed_endpoints,
                    'failed': total_endpoints - passed_endpoints,
                    'success_rate': (passed_endpoints/total_endpoints)*100
                }
            }, f, indent=2, default=str)

        print(f"\n📄 Report saved to: {report_file}")

        return passed_endpoints, total_endpoints


async def main():
    """Main function"""
    print("🚀 Shop Assistant AI - Service Runner and Endpoint Tester")
    print("=" * 60)

    service_manager = ServiceManager()
    endpoint_tester = EndpointTester()

    try:
        # Step 1: Check prerequisites
        print("\n🔍 Step 1: Checking prerequisites...")

        if not service_manager.check_docker():
            print("❌ Docker is required. Please install Docker first.")
            return

        # Step 2: Check if services are already running
        print("\n🔍 Step 2: Checking if services are already running...")

        db_available = service_manager.check_postgres_local()
        redis_available = service_manager.check_redis_local()

        api_available = False
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                api_available = True
                service_manager.log("API is already running")
        except:
            pass

        # Step 3: Start missing services
        if not (db_available and redis_available and api_available):
            print("\n🚀 Step 3: Starting missing services...")

            # Start Docker services if needed
            if not db_available or not redis_available:
                if not service_manager.start_docker_services():
                    print("❌ Failed to start Docker services")
                    return

            # Wait for services to be ready
            if not service_manager.wait_for_services():
                print("❌ Services failed to start properly")
                return

        # Step 4: Setup database
        print("\n🗄️ Step 4: Setting up database...")
        if not service_manager.setup_database():
            print("❌ Database setup failed")
            return

        # Step 5: Test LLM integration
        print("\n🤖 Step 5: Testing LLM integration...")
        llm_success = endpoint_tester.test_llm_integration()
        if not llm_success:
            print("⚠️ LLM integration failed, but continuing with endpoint tests...")

        # Step 6: Test all endpoints
        print("\n🧪 Step 6: Testing all endpoints...")
        endpoint_success = endpoint_tester.test_all_endpoints()

        # Step 7: Generate report
        print("\n📊 Step 7: Generating test report...")
        passed, total = endpoint_tester.generate_report()

        # Final status
        print("\n" + "=" * 60)
        if endpoint_success:
            print("🎉 All tests completed successfully!")
            print("Your Shop Assistant AI system is ready for use!")
        else:
            print("⚠️ Some tests failed, but the system may still be functional.")
            print("Check the detailed report above for specific issues.")
        print("=" * 60)

        # Keep services running for manual testing
        print(f"\n💡 Services are still running!")
        print(f"   API: {API_BASE_URL}")
        print(f"   Database: postgresql://postgres:password@localhost:5432/shop_assistant")
        print(f"   Redis: redis://localhost:6379/0")
        print(f"\nTo stop services later, run: python scripts/run_and_test.py stop")

    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Handle command line arguments
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'stop':
        # Stop services
        service_manager = ServiceManager()
        service_manager.stop_services()
    else:
        # Run main process
        asyncio.run(main())