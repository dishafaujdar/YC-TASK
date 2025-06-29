# hubspot.py
import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis
import urllib.parse

CLIENT_ID = 'f662e950-1fa8-4b4e-933d-d6584f1a5ccb'
CLIENT_SECRET = 'b694843b-38c6-462b-ae47-61bede0b3a09'

# CLIENT_ID = 'XXX'
# CLIENT_SECRET = 'XXX'

encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()   

REDIRECT_URI = 'http://localhost:8080/integrations/hubspot/oauth2callback'   
# Redirect URI (where hubspot will send the response)

# after auth this link get open up
authorization_url = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&scope=crm.objects.contacts.write%20automation%20oauth%20crm.objects.contacts.read&redirect_uri=http://localhost:8080/integrations/hubspot/oauth2callback'


async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)
    
    saved_value = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    print("Saved in Redis ->", saved_value)

    return f'{authorization_url}&state={encoded_state}'


async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')

    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail="Missing authorization code or state")

    state_data = json.loads(encoded_state)  

    print("this is code-> " ,code)
    print("encoded_data -> ", encoded_state)
    print("state_data ->  ", state_data)

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if isinstance(saved_state, bytes):
        saved_state = saved_state.decode("utf-8")  # Convert bytes to string
    
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail=f"State does not match.")
    
    print("saved_state", saved_state)
    print("original_state", original_state)

    print("State Matched Successfully!")

    async with httpx.AsyncClient() as client:
        response_list = await asyncio.gather(
            client.post(
                'https://api.hubapi.com/oauth/v1/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'redirect_uri': REDIRECT_URI,
                    'code': code
                }, 
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded'}
            ),
                delete_key_redis(f'notion_state:{org_id}:{user_id}'),
        )

        response = response_list[0]  
        
        print("Token Exchange Response:", response.status_code, response.text)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {response.text}")
    
    token_data = response.json()
    print("Access Token Response ->", token_data)

    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600) 
    # Once receive the access token, it store it in Redis. Which allows backend to make API requests to Notion on my behalf

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

   
async def get_hubspot_credentials(user_id, org_id):
    # TODO
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    print("credentials -> ",credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    await delete_key_redis(f'hubspot_credentials_credentials:{org_id}:{user_id}')

    return credentials


def _recursive_dict_search(data, target_key):
    """Recursively search for a key in a dictionary of dictionaries."""
    if target_key in data:
        return data[target_key]

    for value in data.values():
        if isinstance(value, dict):
            result = _recursive_dict_search(value, target_key)
            if result is not None:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _recursive_dict_search(item, target_key)
                    if result is not None:
                        return result
    return None


async def create_integration_item_metadata_object(response_json):
    # TODO
    """creates an integration metadata object from the response"""
    name = _recursive_dict_search(response_json['properties'], 'content')
    parent_type = (
        ''
        if response_json['parent']['type'] is None
        else response_json['parent']['type']
    )
    if response_json['parent']['type'] == 'workspace':
        parent_id = None
    else:
        parent_id = (
            response_json['parent'][parent_type]
        )

    name = _recursive_dict_search(response_json, 'content') if name is None else name
    name = 'multi_select' if name is None else name
    name = response_json['object'] + ' ' + name

    integration_item_metadata = IntegrationItem(
        id=response_json['id'],
        type=response_json['object'],
        name=name,
        creation_time=response_json['created_time'],
        last_modified_time=response_json['last_edited_time'],
        parent_id=parent_id,
    )

    return integration_item_metadata


async def get_items_hubspot(credentials):
    # TODO
    """Aggregates all metadata relevant for a hubspot integration"""
    if not credentials:
        print("No credentials are found.")

    credentials = json.loads(credentials)
    print("cred.->>> ",credentials)
    access_token = credentials.get("access_token")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access token")


    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"}
    )
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch HubSpot data")

    data = response.json().get("results", [])

    integration_items = [
        {
            "id": item.get("id"),
            "name": item.get("properties", {}).get("firstname"),
            "email": item.get("properties", {}).get("email"),
            "created_at": item.get("createdAt"),
            "updated_at": item.get("updatedAt"),
        }
        for item in data
    ]

    print("Sample Item:", integration_items[0] if integration_items else "No data found")
    return integration_items



