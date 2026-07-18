import os
from typing import Dict, Any

class ServiceConfig:
    """Configuration for service API connections"""
    
    @staticmethod
    def get_api_config() -> Dict[str, Any]:
        """
        Get API configuration from environment variables or default settings

        Returns:
            Dictionary with API configuration
        """
        return {
            'serper_api_key': os.environ.get('SERPER_API_KEY', ''),
            'milvus_host': os.environ.get('MILVUS_HOST', 'localhost'),
            'milvus_port': int(os.environ.get('MILVUS_PORT', '19530')),
            'policy_collection': os.environ.get('POLICY_COLLECTION', 'policy_documents'),
            # DeepResearch API keys
            'bochaai_api_key': os.environ.get('BOCHA_API_KEY', ''),
            'dashscope_api_key': os.environ.get('DASHSCOPE_API_KEY', ''),
            'dashscope_base_url': os.environ.get('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
        } 
