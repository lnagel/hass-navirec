# Introduction

The Navirec API is a RESTful web service for developers to programmatically interact with Navirec data.

The Navirec API is organized around REST. Every bit of data exchanged between clients and the API is JSON over HTTPS. 
All API requests must be made over HTTPS. Calls made over plain HTTP will fail. You must authenticate for all requests.

The base URL for the Navirec API is https://api.navirec.com/.

If you have questions about using the API, or have come across a bug you'd like to report, write us an email at <api@navirec.com>.

## User-Agent

Set a clearly identifiable User-Agent HTTP header that is unique to your company & integration software being used.
This makes our admin staff fully aware of your integration and allows us to keep your solution fully operational.

Please use only printable ASCII characters.

Examples that we consider a good practice. Please substitute your own names in the examples. 

```http request
User-Agent: MyDomain.com
User-Agent: MyApplication
User-Agent: MyApplication/1.0.0
User-Agent: MyApplication/1.0.0 (python-requests/2.24.0)
```

## Versioning

All API requests should specify the version of the API that the integration was built with.
This version number needs to be appended to the Accept HTTP header as an additional argument.

In the following example, replace `X.Y.Z` with the most recent version number given at the top of the documentation page.

```http request
GET /trips/ HTTP/1.1
Host: api.navirec.com
Accept: application/json; version=X.Y.Z
User-Agent: MyApplication/1.0.0
```

It is possible to use the browsable API without specifying the version, but this is intended
for developer convenience only. All requests made by production systems need to include the 
version in the Accept header. 

## Language

The API will respond with names and labels in English by default. If you wish to receive localized responses,
then you can indicate the preferred language using the following HTTP header:

```http request
Accept-Language: et
```

The response headers will also indicate the content language as a confirmation.

```http request
Content-Language: et
```

## Time zones

The timestamps in the API are represented in the ISO-8601 format including the time zone indicator (Z)
which means these timestamps are in UTC by default. The timestamps shown in the web and mobile apps are in the
account timezone, which is usually not UTC.

If you wish to communicate with the API without converting between local and UTC timestamps, then you can indicate
the timezone you wish to use from the valid IANA timezone identifier list by providing the following HTTP Header:

```http request
Accept-Timezone: Europe/Tallinn
```

The API will respond with the timestamps converted to that timezone including the correct UTC offset indicator.
The response headers will also indicate the content timezone as a confirmation.

```http request
Content-Timezone: Europe/Tallinn
```

## Pagination

Navirec API uses Link Header Pagination for most endpoints (except Last Vehicle States and Last Driver States).

For example when requesting a list of vehicles and the number of objects exceeds 100, then the API will respond with
the first 100 objects and a link to fetch the next 100 objects. The link is stored in the `Link` header with attribute `rel="next"`.
The provided link will have the same query arguments as your original query but with the `cursor` attribute updated.

```http request
GET /vehicles/?ordering=id

HTTP 200 OK
Allow: GET, HEAD, OPTIONS
Content-Type: application/json
Link: <https://api.navirec.com/vehicles/?cursor=cD0wMDQ3N2M4My1jOTYzLTQzYjAtOTM4MC0xNDY1ODY1ZjYwZTg%3D&ordering=id>; rel="next"
Vary: Accept
```

Then you can use that link to fetch the next 100 objects. That response will also include a link to the previous page
with attribute `rel="prev"`.

```http request
GET /vehicles/?cursor=cD0wMDQ3N2M4My1jOTYzLTQzYjAtOTM4MC0xNDY1ODY1ZjYwZTg%3D&ordering=id

HTTP 200 OK
Allow: GET, HEAD, OPTIONS
Content-Type: application/json
Link: 
 <https://api.navirec.com/vehicles/?cursor=cD0wMDhlN2Q0Mi04Mjk5LTQ1YjMtYjc0Ny1hMjZkMjA2YjRiNmE%3D&ordering=id>; rel="next", 
 <https://api.navirec.com/vehicles/?cursor=cj0xJnA9MDA0N2QwNTYtMWFlZS00MDVhLTk4MjctNGI2NWNhNmZjZWY1&ordering=id>; rel="prev"
Vary: Accept
```

When setting a custom `ordering` parameter value in your queries, then we advise to always include a unique
field in your `ordering` parameter to guarantee persistent ordering across queries to different pages. For example
when sorting first by `name`, then append `id` to have the final query argument set to `ordering=name,id`.

Response page size can be customized using the `page_size` query attribute (up to 1000 objects per request).

An excellent documentation describing how link header pagination works has been made available by GitHub on
https://docs.github.com/en/rest/guides/traversing-with-pagination

## Rate limits

Navirec API is rate limited to ensure fair access to available resources. Clients are expected to handle responses 
with status HTTP 429 Too Many Requests appropriately by waiting the number of seconds indicated by the `Retry-After`
response header. In the next example, the API client is expected to wait a minimum of 3 seconds before attempting 
the request again.

```http request
GET /drivers/

HTTP 429 Too Many Requests
Allow: GET, POST, HEAD, OPTIONS
Content-Type: application/json
Retry-After: 3
Vary: Accept

{
    "detail": "Request was throttled. Expected available in 3 seconds."
}
```

An overview of the current limits is provided purely for informative reasons. 
These limits are subject to change without prior notice when necessary to maintain operation.

Session-based limits:

* anonymous: 100/hour
* authenticated sessions: 120/minute, 1800/hour
  
In addition to session-based limits, some endpoints are limited further:

* authenticate: 10/hour
* areas: 24/minute, 400/hour
* trips: 24/minute, 200/hour
* notifications: 24/minute, 200/hour
* vehicle_timeline: 24/minute, 100/hour
* driver_timeline: 24/minute, 100/hour
* vehicle_history: 24/minute, 100/hour
* last_vehicle_states: 24/minute
* last_driver_states: 24/minute
* stream_vehicle_states: 6/minute
* stream_driver_states: 6/minute

## Errors

Navirec uses conventional HTTP response codes to indicate success or failure of an API request. In general, codes in the 2xx range indicate success, codes in the 4xx range indicate an error that resulted from the provided information (e.g. a required parameter was missing, a charge failed, etc.), and codes in the 5xx range indicate an error with Navirec's servers.

| Status code | Status text       | Description                                |
|-------------|-------------------|--------------------------------------------|
| 200         | OK                | Everything                                 |
| 400         | Bad Request       | Often missing a required parameter.        |
| 401         | Unauthorized      | No valid API key provided.                 |
| 402         | Request Failed    | Parameters were valid but request failed.  |
| 404         | Not Found         | The requested item doesn't exist.          |
| 429         | Too Many Requests | Too many requests hit the API too quickly. |
| 50*         | Server Errors     | Something went wrong on our end.           |

## Sideloading

Some list endpoints support sideloading of the related objects. It can be used by providing `sideload` query param. 
Note that this will change response type from List to object and items will have nested lists of requested objects. 

Example request: 

    /emails/?sideload=accounts,drivers,contacts 


Body:

```json    
    {
       "email":[
          ...
       ],
       "accounts":[
          ...
       ],
       "drivers":[
          ...
       ],
       "contacts":[
          ...
       ]
    }
```

## Data streaming

Live GPS tracking data streams of vehicle and driver states is provided with two streaming endpoints:

* `/streams/driver_states/` - returns current driver states and then all subsequent updates
* `/streams/vehicle_states/` - returns current vehicle states and then all subsequent updates

The data format in the streams is compatible with previously available polling endpoints
[last driver states](#tag/Last-driver-states) and [last vehicle states](#tag/Last-vehicle-states).
However, instead of a single JSON list object containing all the state objects, the streaming endpoints 
return state objects in the Newline Delimited JSON (ndjson) Format. 

Query arguments for `/streams/driver_states/`:
 
* `account`
* `driver`
* `driver_group`
* `active`
* `updated_at__gt`

Query arguments for `/streams/vehicle_states/`:

* `account`
* `primary_account`
* `vehicle`
* `vehicles`
* `vehicle_groups`
* `active`
* `updated_at__gt`

Each event in the stream may contain the following fields:

* `id`: a globally unique identifier for the data in the event (optional, only for vehicle_state, driver_state)
* `event`: type of event received (connected, vehicle_state, driver_state, initial_state_sent, heartbeat, disconnected)
* `data`: a json object with data (optional, only for vehicle_state, driver_state)

Event types:

* `connected`: sent at the moment the stream is initialized
* `vehicle_state`: GPS tracking info from a vehicle (only from `/streams/vehicle_states/`)
* `driver_state`: driver state info based on driver recognition tools (only from `/streams/driver_states/`)
* `initial_state_sent`: indicates that the API has sent all currently known state data and will continue to send new state data once it becomes available
* `heartbeat`: sent every 30 seconds to prevent idle connections from timing out
* `disconnected`: sent before recycling the connection in about 1h. the client is expected to reconnect.

Example request:

```http request
GET https://api.navirec.com/streams/vehicle_states/?account=<account_id>

User-Agent: IntegrationApp123
Accept: application/x-ndjson; version=1.33.0
Accept-Timezone: Europe/Tallinn
Authorization: Token eyJ0e..redacted..9ch0A
```

Response stream:

```
{"event":"connected"}
{"id":"f47a0ff0-ccd3-11ee-8001-000000000003","event":"vehicle_state","data":{"id":"f47a0ff0-ccd3-11ee-8001-000000000003","vehicle":"https://api.navirec.com/vehicles/4d7df82d-56a2-45da-bd8a-affacae26606/","time":"2024-02-16T14:02:00.687000Z","location":{"type":"Point","coordinates":[24.88556,59.48166]},"eco_score":10.0,"received_at":"2024-02-16T14:02:00.689000Z","updated_at":"2024-02-16T14:02:01.089216Z","interpolated_at":"2024-02-16T14:02:00.689000Z","streamed_at":"2024-02-16T14:02:09.960173Z","altitude":57,"fuel_level":38.90118364571943,"heading":0,"satellites":8,"speed":0,"total_distance":188300565,"total_engine_time":13614786.765136,"total_fuel_used":30128.871427516962}}
{"id":"f6e347c0-ccd3-11ee-8001-000000000001","event":"vehicle_state","data":{"id":"f6e347c0-ccd3-11ee-8001-000000000001","vehicle":"https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/","time":"2024-02-16T14:02:04.732000Z","location":{"type":"Point","coordinates":[24.931966111111112,59.442189]},"eco_score":9.2,"received_at":"2024-02-16T14:02:04.733000Z","updated_at":"2024-02-16T14:02:04.907823Z","interpolated_at":"2024-02-16T14:02:04.733000Z","streamed_at":"2024-02-16T14:02:09.963621Z","altitude":24,"digital_input_1":false,"digital_input_2":false,"digital_input_3":false,"digital_input_4":true,"fuel_level":82.33332724573575,"heading":321,"ignition":true,"satellites":20,"speed":47,"supply_voltage":14.356,"total_distance":186588673,"total_engine_time":13517008.166329,"total_fuel_used":22391.22350873688}}
{"event":"initial_state_sent"}
{"id":"fa6ff0f0-ccd3-11ee-8001-000000000003","event":"vehicle_state","data":{"id":"fa6ff0f0-ccd3-11ee-8001-000000000003","vehicle":"https://api.navirec.com/vehicles/4d7df82d-56a2-45da-bd8a-affacae26606/","time":"2024-02-16T14:02:10.687000Z","location":{"type":"Point","coordinates":[24.88556,59.48166]},"eco_score":10.0,"activity_started_at":null,"received_at":"2024-02-16T14:02:10.688000Z","updated_at":"2024-02-16T14:02:11.633993Z","interpolated_at":"2024-02-16T14:02:10.688000Z","streamed_at":"2024-02-16T14:02:11.603969Z","altitude":58,"fuel_level":38.90118364571943,"heading":0,"satellites":8,"speed":0,"total_distance":188300565,"total_engine_time":13614786.765136,"total_fuel_used":30128.871427516962}}
{"id":"fb7c30d0-ccd3-11ee-8001-000000000001","event":"vehicle_state","data":{"id":"fb7c30d0-ccd3-11ee-8001-000000000001","vehicle":"https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/","time":"2024-02-16T14:02:12.445000Z","location":{"type":"Point","coordinates":[24.931194,59.442674]},"eco_score":9.2,"activity_started_at":null,"received_at":"2024-02-16T14:02:12.446000Z","updated_at":"2024-02-16T14:02:13.066519Z","interpolated_at":"2024-02-16T14:02:12.446000Z","streamed_at":"2024-02-16T14:02:13.114918Z","altitude":25,"digital_input_1":false,"digital_input_2":false,"digital_input_3":false,"digital_input_4":true,"fuel_level":82.32149962214419,"heading":321,"ignition":true,"satellites":20,"speed":46,"supply_voltage":14.39,"total_distance":186588772,"total_engine_time":13517015.879997,"total_fuel_used":22391.23533636047}}
{"id":"ffead590-ccd3-11ee-8001-000000000001","event":"vehicle_state","data":{"id":"ffead590-ccd3-11ee-8001-000000000001","vehicle":"https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/","time":"2024-02-16T14:02:19.881000Z","location":{"type":"Point","coordinates":[24.930544,59.443188]},"eco_score":9.2,"activity_started_at":null,"received_at":"2024-02-16T14:02:19.884000Z","updated_at":"2024-02-16T14:02:21.653110Z","interpolated_at":"2024-02-16T14:02:19.884000Z","streamed_at":"2024-02-16T14:02:21.623079Z","altitude":25,"digital_input_1":false,"digital_input_2":false,"digital_input_3":false,"digital_input_4":true,"fuel_level":82.30992479600353,"heading":333,"ignition":true,"satellites":20,"speed":49,"supply_voltage":14.388,"total_distance":186588868,"total_engine_time":13517023.315323,"total_fuel_used":22391.24691118661}}
{"id":"0065d1f0-ccd4-11ee-8001-000000000003","event":"vehicle_state","data":{"id":"0065d1f0-ccd4-11ee-8001-000000000003","vehicle":"https://api.navirec.com/vehicles/4d7df82d-56a2-45da-bd8a-affacae26606/","time":"2024-02-16T14:02:20.687000Z","location":{"type":"Point","coordinates":[24.88556,59.48166]},"eco_score":10.0,"activity_started_at":null,"received_at":"2024-02-16T14:02:20.689000Z","updated_at":"2024-02-16T14:02:21.654434Z","interpolated_at":"2024-02-16T14:02:20.689000Z","streamed_at":"2024-02-16T14:02:21.624709Z","altitude":59,"fuel_level":38.90118364571943,"heading":0,"satellites":8,"speed":0,"total_distance":188300565,"total_engine_time":13614786.765136,"total_fuel_used":30128.871427516962}}
{"event":"heartbeat"}
{"id":"09f99a30-ccd4-11ee-8001-000000000001","event":"vehicle_state","data":{"id":"09f99a30-ccd4-11ee-8001-000000000001","vehicle":"https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/","time":"2024-02-16T14:02:36.755000Z","location":{"type":"Point","coordinates":[24.92939,59.444748]},"eco_score":9.2,"activity_started_at":null,"received_at":"2024-02-16T14:02:36.758000Z","updated_at":"2024-02-16T14:02:38.715554Z","interpolated_at":"2024-02-16T14:02:36.758000Z","streamed_at":"2024-02-16T14:02:38.685932Z","altitude":27,"digital_input_1":false,"digital_input_2":false,"digital_input_3":true,"digital_input_4":true,"fuel_level":82.28318246588582,"heading":2,"ignition":true,"satellites":20,"speed":47,"supply_voltage":14.393,"total_distance":186589091,"total_engine_time":13517040.190096,"total_fuel_used":22391.273653516728}}
{"id":"0b88c5b0-ccd4-11ee-8001-000000000001","event":"vehicle_state","data":{"id":"0b88c5b0-ccd4-11ee-8001-000000000001","vehicle":"https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/","time":"2024-02-16T14:02:39.371000Z","location":{"type":"Point","coordinates":[24.929488,59.445061]},"eco_score":9.2,"activity_started_at":null,"received_at":"2024-02-16T14:02:39.373000Z","updated_at":"2024-02-16T14:02:40.715671Z","interpolated_at":"2024-02-16T14:02:39.373000Z","streamed_at":"2024-02-16T14:02:40.686831Z","altitude":28,"digital_input_1":false,"digital_input_2":false,"digital_input_3":true,"digital_input_4":true,"fuel_level":82.27917120058504,"heading":9,"ignition":true,"satellites":20,"speed":46,"supply_voltage":14.385,"total_distance":186589124,"total_engine_time":13517042.806139,"total_fuel_used":22391.27766478203}}
{"id":"0c5193f0-ccd4-11ee-8001-000000000003","event":"vehicle_state","data":{"id":"0c5193f0-ccd4-11ee-8001-000000000003","vehicle":"https://api.navirec.com/vehicles/4d7df82d-56a2-45da-bd8a-affacae26606/","time":"2024-02-16T14:02:40.687000Z","location":{"type":"Point","coordinates":[24.88556,59.48166]},"eco_score":10.0,"activity_started_at":null,"received_at":"2024-02-16T14:02:40.688000Z","updated_at":"2024-02-16T14:02:41.127646Z","interpolated_at":"2024-02-16T14:02:40.688000Z","streamed_at":"2024-02-16T14:02:41.097539Z","altitude":60,"fuel_level":38.90118364571943,"heading":0,"satellites":8,"speed":0,"total_distance":188300565,"total_engine_time":13614786.765136,"total_fuel_used":30128.871427516962}}
{"event":"heartbeat"}
{"event":"disconnected"}
```

The streams are kept open from the API side until either the client terminates the request or the server process
restarts (e.g. during a software update or container restart). In this case, the client may reconnect to the stream
and provide the last known `updated_at` timestamp to re-initialize the stream at that position.

Then the next API call should be like this:

```http request
GET https://api.navirec.com/streams/vehicle_states/?account=<account_id>&updated_at__gt=2024-02-16T14:02:41.127646Z
```

# Authentication

Please use the Navirec web application to generate an API token.
The API token management page is located in Profile menu -> Account settings -> 
[API access](https://app.navirec.com/account/api-access/).

After creating the access token for a new integration, you must also assign permissions to the newly
created integration user. Click on the integration name in the table to edit permissions.

For clients to authenticate, the token key should be included in the Authorization HTTP header.
The key should be prefixed by the string literal "Token", with whitespace separating the two strings.

`Authorization: Token eyJhbGc.example.ssw5c`
    
Note: you must replace `eyJhbGc.example.ssw5c` with the newly created API token.
