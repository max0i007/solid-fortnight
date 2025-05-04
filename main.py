import json
import random
import re
import base64
import logging
from typing import Optional, List, Dict, Any, Union
import os
import random

import requests
from fastapi import FastAPI, Query, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("netfree_api")

app = FastAPI(
    title="NetFree API",
    description="API to fetch content from netfree2.cc",
    version="1.0.2"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response models
class StatusModel(BaseModel):
    code: int
    success: bool
    error: Optional[str] = None

class Source(BaseModel):
    file: str
    label: str
    type: str
    default: Optional[bool] = None

class PlaylistData(BaseModel):
    sources: Optional[List[Source]] = None

class ResponseData(BaseModel):
    type: str
    format: Optional[str] = None
    data: Union[str, Dict[str, Any], List[Dict[str, Any]]]

class ApiResponse(BaseModel):
    status: StatusModel
    data: Dict[str, Any]

class HLSUrl(BaseModel):
    quality: str
    url: str
    type: str
    default: bool

class HLSResponse(BaseModel):
    hls_urls: List[HLSUrl]

# Middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

# List of common user agents to rotate through
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
]

# Cookie store - in a production environment, this should be in a database or Redis
# For simplicity, we'll store them in memory in this example
COOKIES_CACHE = {
    'default': 'user_token=c4e606ec3f66b93e8198a48c8c71e6b8; t_hash_t=4184321d319f63c93cff4c7588764623%3A%3A14b66f534e8c2fa68723668dead845ce%3A%3A1746367568%3A%3Ani; recentplay=81688854; 81688854=95%3A7065'
}

async def get_fresh_cookies():
    """Function to get fresh cookies from the site"""
    try:
        session = requests.Session()
        # Use a random user agent
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1'
        }
        
        # First visit homepage to get initial cookies
        response = session.get('https://netfree2.cc/home', headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Extract the cookies as a string
            cookie_dict = session.cookies.get_dict()
            cookie_string = '; '.join([f'{k}={v}' for k, v in cookie_dict.items()])
            logger.info(f"Successfully obtained fresh cookies: {cookie_string}")
            
            # Store in cache
            COOKIES_CACHE['latest'] = cookie_string
            return cookie_string
        else:
            logger.warning(f"Failed to get fresh cookies, status code: {response.status_code}")
            return COOKIES_CACHE['default']
    except Exception as e:
        logger.error(f"Error getting fresh cookies: {str(e)}")
        return COOKIES_CACHE['default']

ROXIES = [
    "http://40.76.69.94:8080",
    "http://88.99.209.189:1234",
    "http://67.43.228.251:21621",
    "http://8.219.97.248:80",
    "http://119.156.195.173:3128",
    "http://34.102.48.89:8080",
    "http://45.140.143.77:18080",
    "http://3.110.60.103:80",
    "http://200.174.198.86:8888",
    "http://34.143.143.61:7777",
    "http://72.10.160.173:11025",
    "http://91.243.226.71:8080",
    "http://44.220.205.79:8080"
]

def get_random_proxy():
    return random.choice(PROXIES)

def make_request(id: str, t: str, tm: str, use_fresh_cookies: bool = False):
    url = f'https://netfree2.cc/playlist.php?id={id}&t={t}&tm={tm}'
    logger.info(f"Making request to {url}")

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Host': 'netfree2.cc',
        'Referer': 'https://netfree2.cc/home',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'TE': 'trailers',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0'
    }

    if not use_fresh_cookies:
        headers['Cookie'] = 'user_token=c4e606ec3f66b93e8198a48c8c71e6b8; t_hash_t=4184321d319f63c93cff4c7588764623%3A%3A14b66f534e8c2fa68723668dead845ce%3A%3A1746367568%3A%3Ani; recentplay=81688854; 81688854=95%3A7065'

    proxy = get_random_proxy()
    logger.info(f"Using proxy: {proxy}")

    try:
        response = requests.get(url, headers=headers, proxies={"http": proxy, "https": proxy}, timeout=10)
        logger.info(f"Response status code: {response.status_code}")
        return {
            'http_code': response.status_code,
            'response': response.content,
            'error': None
        }
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return {
            'http_code': 408,
            'response': None,
            'error': "Request timed out"
        }
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return {
            'http_code': 503,
            'response': None,
            'error': f"Connection error: {e}"
        }
    except Exception as e:
        logger.error(f"Exception during request: {str(e)}", exc_info=True)
        return {
            'http_code': 0,
            'response': None,
            'error': str(e)
        }

def detect_binary_format(data):
    if not isinstance(data, bytes):
        return 'text/plain'

    if data.startswith(b'\xff\xd8'):
        return 'image/jpeg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return 'image/gif'
    elif data.startswith(b'\x00\x00\x00\x1cftyp'):
        return 'video/mp4'
    elif data.startswith(b'\x1aE\xdf\xa3'):
        return 'video/webm'
    elif data.startswith(b'ID3') or data.startswith(b'\xff\xfb') or data.startswith(b'\xff\xf3'):
        return 'audio/mpeg'
    else:
        return 'application/octet-stream'

def process_response(response_raw):
    if not response_raw:
        logger.warning("Empty response received")
        return {
            'type': 'text',
            'data': ''
        }

    if isinstance(response_raw, bytes) and re.search(b'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', response_raw):
        format_type = detect_binary_format(response_raw)
        logger.info(f"Binary content detected, format: {format_type}")
        return {
            'type': 'binary',
            'format': format_type,
            'data': base64.b64encode(response_raw).decode('utf-8')
        }

    if isinstance(response_raw, bytes):
        try:
            response_str = response_raw.decode('utf-8')
            logger.info("Successfully decoded response as UTF-8")
        except UnicodeDecodeError:
            logger.warning("Failed to decode as UTF-8, treating as binary")
            return {
                'type': 'binary',
                'format': 'application/octet-stream',
                'data': base64.b64encode(response_raw).decode('utf-8')
            }
    else:
        response_str = response_raw
        logger.info("Response was already a string, no decoding needed")

    try:
        decoded = json.loads(response_str)
        logger.info("Response successfully parsed as JSON")
        return {
            'type': 'json',
            'data': decoded
        }
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse as JSON ({str(e)}), treating as plain text")
        return {
            'type': 'text',
            'data': response_str
        }

@app.get("/refresh-cookies")
async def refresh_cookies():
    """Endpoint to manually refresh the cookies cache"""
    try:
        new_cookies = await get_fresh_cookies()
        return {
            "status": "success",
            "message": "Cookies refreshed successfully",
            "cookies_length": len(new_cookies)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to refresh cookies: {str(e)}"
        }

@app.get("/playlist/", response_model=ApiResponse)
async def get_playlist(
    id: str = Query(..., description="Content ID"),
    t: str = Query(..., description="Title parameter"),
    tm: str = Query(..., description="TM parameter"),
    fresh_cookies: bool = Query(False, description="Use fresh cookies instead of saved ones")
):
    logger.info(f"Request received for ID: {id}, Title: {t}, TM: {tm}, Fresh cookies: {fresh_cookies}")
    
    # If using fresh cookies, make sure we have them
    if fresh_cookies and 'latest' not in COOKIES_CACHE:
        await get_fresh_cookies()
    
    request_result = make_request(id, t, tm, fresh_cookies)
    response_raw = request_result['response']
    http_code = request_result['http_code']
    error_message = request_result['error']

    # If we get an error that could be due to expired cookies, try refreshing them
    if (http_code >= 400 or error_message) and fresh_cookies:
        logger.info("Request failed, trying to refresh cookies and retry")
        await get_fresh_cookies()
        request_result = make_request(id, t, tm, True)  # Use fresh cookies
        response_raw = request_result['response']
        http_code = request_result['http_code']
        error_message = request_result['error']

    processed_data = process_response(response_raw)
    if isinstance(processed_data, dict) and processed_data.get('type') == 'json':
        if isinstance(processed_data['data'], list) and len(processed_data['data']) > 0:
            processed_data['data'] = processed_data['data'][0]

    if http_code == 200 and isinstance(processed_data, dict) and processed_data.get('type') == 'text':
        if "404 Not Found" in processed_data.get('data', ""):
            http_code = 404
            error_message = "Resource not found on netfree2.cc"
        elif "Access denied" in processed_data.get('data', ""):
            http_code = 403
            error_message = "Access denied - authentication required"

    api_response = {
        'status': {
            'code': http_code,
            'success': (http_code >= 200 and http_code < 300 and not error_message),
            'error': error_message
        },
        'data': processed_data
    }

    logger.info(f"Returning response with status code: {http_code}, success: {api_response['status']['success']}")
    return api_response

@app.get("/")
async def root():
    return {
        "message": "NetFree API Service",
        "usage": "Make GET requests to /playlist/ with id, t, and tm parameters",
        "example": "/playlist/?id=81900595&t=Mad%20Square&tm=14170286",
        "options": "Add fresh_cookies=true to use fresh cookies instead of saved ones",
        "cookie_refresh": "/refresh-cookies to manually refresh the cookie cache",
        "debug": "Check server logs for detailed request/response information",
        "version": "1.0.2"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.2"
    }

@app.get("/hls/", response_model=HLSResponse)
async def get_hls_url(
    id: str = Query(..., description="Content ID"),
    t: str = Query(..., description="Title parameter"),
    tm: str = Query(..., description="TM parameter"),
    fresh_cookies: bool = Query(False, description="Use fresh cookies instead of saved ones")
):
    logger.info(f"HLS URL request for ID: {id}, Title: {t}, TM: {tm}")
    response = await get_playlist(id, t, tm, fresh_cookies)

    data = response['data']
    sources = None

    if isinstance(data, dict):
        if data.get('type') == 'json' and isinstance(data.get('data'), dict):
            sources = data['data'].get('sources')
        elif 'sources' in data:
            sources = data['sources']

    if not sources:
        error_detail = "HLS URL not found in response"
        logger.error(error_detail)
        raise HTTPException(status_code=404, detail=error_detail)

    hls_urls = [{
        'quality': source.get('label', 'Unknown'),
        'url': f"https://netfree2.cc{source['file']}" if not source['file'].startswith('http') else source['file'],
        'type': source.get('type', 'Unknown'),
        'default': source.get('default', False)
    } for source in sources]

    logger.info(f"Found {len(hls_urls)} HLS URLs")
    return {"hls_urls": hls_urls}

@app.get("/example/", response_model=ApiResponse)
async def example_request(fresh_cookies: bool = Query(False, description="Use fresh cookies instead of saved ones")):
    logger.info("Example request triggered")
    return await get_playlist(
        id="81900595",
        t="Mad Square",
        tm="14170286",
        fresh_cookies=fresh_cookies
    )

@app.get("/debug/headers/")
async def debug_headers(request: Request):
    return {
        "headers": dict(request.headers),
        "client": request.client.host,
        "cookies_cache_status": {
            "default_cookie_length": len(COOKIES_CACHE['default']),
            "has_fresh_cookies": 'latest' in COOKIES_CACHE,
            "fresh_cookie_length": len(COOKIES_CACHE.get('latest', '')) if 'latest' in COOKIES_CACHE else 0
        }
    }

# Initialize by getting fresh cookies when app starts
@app.on_event("startup")
async def startup_event():
    logger.info("Starting NetFree API server and initializing cookie cache")
    try:
        await get_fresh_cookies()
    except Exception as e:
        logger.warning(f"Failed to get initial fresh cookies: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting NetFree API server")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
