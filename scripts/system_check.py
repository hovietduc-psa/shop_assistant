#!/usr/bin/env python3
"""
Comprehensive System Check and Debugging Script
Tests all major components of the Shop Assistant AI system
"""

import asyncio
import os
import sys
import json
import requests
import time
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.core.llm.llm_manager import LLMManager
from app.core.llm.prompt_templates import PromptManager
from app.integrations.shopify.client import ShopifyClient
from app.core.intelligence.escalation import EscalationEngine
from app.core.intelligence.quality import QualityAssessor
from app.core.intelligence.sentiment import SentimentAnalyzer
from app.core.intelligence.coaching import CoachingEngine


class SystemChecker:
    """Comprehensive system health checker"""

    def __init__(self):
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {},
            'overall_status': 'unknown'
        }

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

    def check_environment_variables(self):
        """Check all required environment variables"""
        self.log("Checking environment variables...")

        required_vars = {
            'OPENROUTER_API_KEY': settings.OPENROUTER_API_KEY,
            'COHERE_API_KEY': settings.COHERE_API_KEY,
            'SHOPIFY_SHOP_DOMAIN': settings.SHOPIFY_SHOP_DOMAIN,
            'SHOPIFY_ACCESS_TOKEN': settings.SHOPIFY_ACCESS_TOKEN,
            'DATABASE_URL': settings.DATABASE_URL,
            'REDIS_URL': settings.REDIS_URL
        }

        missing_vars = []
        for var_name, var_value in required_vars.items():
            if not var_value or var_value.startswith('your-'):
                missing_vars.append(var_name)
                self.log(f"Missing or placeholder value for {var_name}", 'fail')
            else:
                # Mask sensitive values in logs
                masked_value = var_value[:8] + "..." if len(var_value) > 8 else "configured"
                self.log(f"{var_name}: {masked_value}", 'pass')

        if missing_vars:
            self.results['checks']['environment'] = {
                'status': 'fail',
                'missing_vars': missing_vars
            }
            self.log("Environment check failed!", 'fail')
        else:
            self.results['checks']['environment'] = {
                'status': 'pass',
                'message': 'All environment variables configured'
            }
            self.log("Environment variables configured correctly", 'pass')

        return len(missing_vars) == 0

    async def check_llm_manager(self):
        """Test LLM Manager functionality"""
        self.log("Testing LLM Manager...")

        try:
            llm_manager = LLMManager()

            # Test basic LLM call
            test_prompt = "Respond with 'LLM test successful' in JSON format."
            response = await llm_manager.generate_response(
                prompt=test_prompt,
                max_tokens=50,
                temperature=0.1
            )

            if response and 'content' in response:
                self.log(f"LLM response: {response['content'][:50]}...", 'pass')
                self.results['checks']['llm_manager'] = {
                    'status': 'pass',
                    'response_preview': response['content'][:100]
                }
            else:
                self.log("Invalid LLM response format", 'fail')
                self.results['checks']['llm_manager'] = {
                    'status': 'fail',
                    'error': 'Invalid response format'
                }
                return False

            # Test embedding generation
            test_text = "This is a test for embedding generation."
            embedding = await llm_manager.generate_embedding(test_text)

            if embedding and len(embedding) > 0:
                self.log(f"Embedding generated successfully (length: {len(embedding)})", 'pass')
                self.results['checks']['embedding'] = {
                    'status': 'pass',
                    'embedding_length': len(embedding)
                }
            else:
                self.log("Embedding generation failed", 'fail')
                self.results['checks']['embedding'] = {
                    'status': 'fail',
                    'error': 'No embedding generated'
                }
                return False

            return True

        except Exception as e:
            self.log(f"LLM Manager error: {str(e)}", 'fail')
            self.results['checks']['llm_manager'] = {
                'status': 'fail',
                'error': str(e)
            }
            return False

    async def check_shopify_integration(self):
        """Test Shopify API integration"""
        self.log("Testing Shopify integration...")

        try:
            shopify_client = ShopifyClient(
                shop_domain=settings.SHOPIFY_SHOP_DOMAIN,
                access_token=settings.SHOPIFY_ACCESS_TOKEN
            )

            # Test product search
            search_result = await shopify_client.search_products(
                query="test",
                limit=5
            )

            if search_result:
                products, has_more = search_result
                self.log(f"Shopify search successful: {len(products)} products found", 'pass')
                self.results['checks']['shopify'] = {
                    'status': 'pass',
                    'products_found': len(products),
                    'has_more': has_more
                }

                # Test individual product if available
                if products:
                    product = products[0]
                    self.log(f"Sample product: {product.get('title', 'Unknown')[:30]}...", 'info')
            else:
                self.log("Shopify search returned no results", 'warn')
                self.results['checks']['shopify'] = {
                    'status': 'warn',
                    'message': 'Search returned no results'
                }

            return True

        except Exception as e:
            self.log(f"Shopify integration error: {str(e)}", 'fail')
            self.results['checks']['shopify'] = {
                'status': 'fail',
                'error': str(e)
            }
            return False

    async def check_intelligence_systems(self):
        """Test all AI intelligence systems"""
        self.log("Testing AI Intelligence Systems...")

        try:
            llm_manager = LLMManager()
            prompt_manager = PromptManager()

            # Test conversation data
            test_conversation = {
                "conversation_id": "test_conv_001",
                "messages": [
                    {"role": "customer", "content": "I'm frustrated with my order!"},
                    {"role": "agent", "content": "I understand your frustration and want to help."}
                ]
            }

            intelligence_results = {}

            # Test Escalation Engine
            try:
                escalation_engine = EscalationEngine(llm_manager, prompt_manager)
                from app.core.intelligence.models import EscalationRequest
                escalation_request = EscalationRequest(
                    conversation_id=test_conversation["conversation_id"],
                    messages=test_conversation["messages"]
                )
                escalation_result = await escalation_engine.analyze_escalation(escalation_request)

                if escalation_result:
                    intelligence_results['escalation'] = {
                        'status': 'pass',
                        'should_escalate': escalation_result.decision.should_escalate,
                        'confidence': escalation_result.decision.confidence
                    }
                    self.log(f"Escalation engine working: Should escalate = {escalation_result.decision.should_escalate}", 'pass')
                else:
                    intelligence_results['escalation'] = {'status': 'fail', 'error': 'No result'}
                    self.log("Escalation engine failed to produce result", 'fail')
            except Exception as e:
                intelligence_results['escalation'] = {'status': 'fail', 'error': str(e)}
                self.log(f"Escalation engine error: {str(e)}", 'fail')

            # Test Quality Assessor
            try:
                quality_assessor = QualityAssessor(llm_manager, prompt_manager)
                from app.core.intelligence.models import QualityAssessmentRequest
                quality_request = QualityAssessmentRequest(
                    conversation_id=test_conversation["conversation_id"],
                    messages=test_conversation["messages"]
                )
                quality_result = await quality_assessor.assess_conversation_quality(quality_request)

                if quality_result:
                    intelligence_results['quality'] = {
                        'status': 'pass',
                        'score': quality_result.numeric_score,
                        'quality_level': quality_result.overall_score.value
                    }
                    self.log(f"Quality assessor working: Score = {quality_result.numeric_score}/10", 'pass')
                else:
                    intelligence_results['quality'] = {'status': 'fail', 'error': 'No result'}
                    self.log("Quality assessor failed to produce result", 'fail')
            except Exception as e:
                intelligence_results['quality'] = {'status': 'fail', 'error': str(e)}
                self.log(f"Quality assessor error: {str(e)}", 'fail')

            # Test Sentiment Analyzer
            try:
                sentiment_analyzer = SentimentAnalyzer(llm_manager, prompt_manager)
                sentiment_result = await sentiment_analyzer.analyze_sentiment(test_conversation["messages"])

                if sentiment_result:
                    intelligence_results['sentiment'] = {
                        'status': 'pass',
                        'sentiment': sentiment_result.overall_sentiment.value,
                        'score': sentiment_result.sentiment_score
                    }
                    self.log(f"Sentiment analyzer working: Sentiment = {sentiment_result.overall_sentiment.value}", 'pass')
                else:
                    intelligence_results['sentiment'] = {'status': 'fail', 'error': 'No result'}
                    self.log("Sentiment analyzer failed to produce result", 'fail')
            except Exception as e:
                intelligence_results['sentiment'] = {'status': 'fail', 'error': str(e)}
                self.log(f"Sentiment analyzer error: {str(e)}", 'fail')

            self.results['checks']['intelligence'] = intelligence_results

            # Count successful intelligence systems
            successful_systems = sum(1 for result in intelligence_results.values() if result['status'] == 'pass')
            total_systems = len(intelligence_results)

            if successful_systems == total_systems:
                self.log(f"All {total_systems} intelligence systems working correctly", 'pass')
                return True
            else:
                self.log(f"{successful_systems}/{total_systems} intelligence systems working", 'warn')
                return False

        except Exception as e:
            self.log(f"Intelligence systems error: {str(e)}", 'fail')
            self.results['checks']['intelligence'] = {
                'status': 'fail',
                'error': str(e)
            }
            return False

    def check_api_endpoints(self):
        """Test API endpoints"""
        self.log("Testing API endpoints...")

        base_url = "http://localhost:8000"
        endpoints = [
            {"path": "/", "method": "GET", "description": "Root endpoint"},
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/api/v1/", "method": "GET", "description": "API root"},
        ]

        api_results = {}
        successful_endpoints = 0

        for endpoint in endpoints:
            url = f"{base_url}{endpoint['path']}"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code < 400:
                    api_results[endpoint['path']] = {
                        'status': 'pass',
                        'status_code': response.status_code,
                        'response_time': response.elapsed.total_seconds()
                    }
                    successful_endpoints += 1
                    self.log(f"✓ {endpoint['description']} ({response.status_code})", 'pass')
                else:
                    api_results[endpoint['path']] = {
                        'status': 'fail',
                        'status_code': response.status_code,
                        'error': response.text[:100]
                    }
                    self.log(f"✗ {endpoint['description']} ({response.status_code})", 'fail')
            except requests.exceptions.RequestException as e:
                api_results[endpoint['path']] = {
                    'status': 'fail',
                    'error': str(e)
                }
                self.log(f"✗ {endpoint['description']} - Connection failed", 'fail')

        self.results['checks']['api'] = api_results

        if successful_endpoints == len(endpoints):
            self.log("All API endpoints working correctly", 'pass')
            return True
        else:
            self.log(f"{successful_endpoints}/{len(endpoints)} endpoints working", 'warn')
            return False

    def check_database_connection(self):
        """Test database connection"""
        self.log("Testing database connection...")

        try:
            from app.core.database import engine
            from sqlalchemy import text

            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                if result.fetchone():
                    self.log("Database connection successful", 'pass')
                    self.results['checks']['database'] = {
                        'status': 'pass',
                        'message': 'Connected successfully'
                    }
                    return True
                else:
                    self.log("Database query failed", 'fail')
                    self.results['checks']['database'] = {
                        'status': 'fail',
                        'error': 'Query failed'
                    }
                    return False
        except Exception as e:
            self.log(f"Database connection error: {str(e)}", 'fail')
            self.results['checks']['database'] = {
                'status': 'fail',
                'error': str(e)
            }
            return False

    def check_redis_connection(self):
        """Test Redis connection"""
        self.log("Testing Redis connection...")

        try:
            import redis

            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.ping()

            self.log("Redis connection successful", 'pass')
            self.results['checks']['redis'] = {
                'status': 'pass',
                'message': 'Connected successfully'
            }
            return True
        except Exception as e:
            self.log(f"Redis connection error: {str(e)}", 'fail')
            self.results['checks']['redis'] = {
                'status': 'fail',
                'error': str(e)
            }
            return False

    def generate_report(self):
        """Generate comprehensive system report"""
        total_checks = len(self.results['checks'])
        passed_checks = sum(1 for check in self.results['checks'].values() if check['status'] == 'pass')
        failed_checks = sum(1 for check in self.results['checks'].values() if check['status'] == 'fail')
        warned_checks = sum(1 for check in self.results['checks'].values() if check['status'] == 'warn')

        if failed_checks == 0:
            overall_status = 'pass'
            status_emoji = '🎉'
        elif failed_checks <= 2:
            overall_status = 'warn'
            status_emoji = '⚠️'
        else:
            overall_status = 'fail'
            status_emoji = '❌'

        self.results['overall_status'] = overall_status
        self.results['summary'] = {
            'total_checks': total_checks,
            'passed': passed_checks,
            'failed': failed_checks,
            'warned': warned_checks
        }

        # Print summary
        print(f"\n{status_emoji} SYSTEM CHECK SUMMARY")
        print(f"=" * 50)
        print(f"Total Checks: {total_checks}")
        print(f"Passed: {passed_checks} ✅")
        print(f"Failed: {failed_checks} ❌")
        print(f"Warnings: {warned_checks} ⚠️")
        print(f"Overall Status: {overall_status.upper()}")

        # Print detailed results
        print(f"\n📋 DETAILED RESULTS")
        print(f"=" * 50)
        for check_name, result in self.results['checks'].items():
            status_icon = {'pass': '✅', 'fail': '❌', 'warn': '⚠️'}.get(result['status'], '❓')
            print(f"{status_icon} {check_name.upper()}: {result['status'].upper()}")
            if 'error' in result:
                print(f"   Error: {result['error']}")

        # Save report to file
        report_file = f"system_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\n📄 Detailed report saved to: {report_file}")

        return overall_status

    async def run_all_checks(self):
        """Run all system checks"""
        self.log("🚀 Starting comprehensive system check...")

        check_functions = [
            ('Environment Variables', self.check_environment_variables),
            ('Database Connection', self.check_database_connection),
            ('Redis Connection', self.check_redis_connection),
            ('LLM Manager', self.check_llm_manager),
            ('Shopify Integration', self.check_shopify_integration),
            ('Intelligence Systems', self.check_intelligence_systems),
            ('API Endpoints', self.check_api_endpoints),
        ]

        for check_name, check_function in check_functions:
            try:
                if asyncio.iscoroutinefunction(check_function):
                    await check_function()
                else:
                    check_function()
            except Exception as e:
                self.log(f"Critical error in {check_name}: {str(e)}", 'fail')
                self.results['checks'][check_name.lower().replace(' ', '_')] = {
                    'status': 'fail',
                    'error': str(e)
                }

        return self.generate_report()


async def main():
    """Main function"""
    print("🔍 Shop Assistant AI - System Health Checker")
    print("=" * 50)

    checker = SystemChecker()

    # Check if server is running first
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running on http://localhost:8000")
        else:
            print("⚠️ Server responded but may have issues")
    except requests.exceptions.RequestException:
        print("❌ Server is not running on http://localhost:8000")
        print("   Please start the server first with: uvicorn app.main:app --reload")
        return

    print("\n" + "=" * 50)

    # Run all checks
    overall_status = await checker.run_all_checks()

    print("\n" + "=" * 50)
    if overall_status == 'pass':
        print("🎉 All systems operational! Ready for use.")
    elif overall_status == 'warn':
        print("⚠️ System mostly operational, but some warnings detected.")
    else:
        print("❌ System has critical issues that need attention.")

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())