# API reference

The router implements every endpoint in
[mygpo OpenAPI 2.11.0](https://github.com/gpodder/mygpo/blob/master/mygpo/api/openapi.yaml).

For interactive exploration, run the server and open:

- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:8000/redoc` — ReDoc
- `http://localhost:8000/openapi.json` — schema

## Endpoint summary

### Client parametrization

| Method | Path                 | Description                  |
|--------|----------------------|------------------------------|
| GET    | `/clientconfig.json` | mygpo / feedservice base URLs |

### Authentication

| Method | Path                                       |
|--------|--------------------------------------------|
| POST   | `/api/2/auth/{username}/login.json`        |
| POST   | `/api/2/auth/{username}/logout.json`       |
| POST   | `/api/2/auth/{username}/register.json` *(extension)* |

### Directory

| Method | Path                                |
|--------|-------------------------------------|
| GET    | `/api/2/tags/{count}.json`          |
| GET    | `/api/2/tag/{tag}/{count}.json`     |
| GET    | `/api/2/data/podcast.json`          |
| GET    | `/api/2/data/episode.json`          |
| GET    | `/toplist/{number}.{format}`        |
| GET    | `/search.{format}`                  |

### Suggestions

| Method | Path                                  |
|--------|---------------------------------------|
| GET    | `/suggestions/{number}.{format}`      |

### Devices

| Method | Path                                              |
|--------|---------------------------------------------------|
| GET    | `/api/2/devices/{username}.json`                  |
| POST   | `/api/2/devices/{username}/{deviceid}.json`       |
| GET    | `/api/2/updates/{username}/{deviceid}.json`       |

### Device synchronisation

| Method | Path                                  |
|--------|---------------------------------------|
| GET    | `/api/2/sync-devices/{username}.json` |
| POST   | `/api/2/sync-devices/{username}.json` |

### Subscriptions (simple)

| Method | Path                                                    |
|--------|---------------------------------------------------------|
| GET    | `/subscriptions/{username}/{deviceid}.{format}`         |
| PUT    | `/subscriptions/{username}/{deviceid}.{format}`         |
| GET    | `/subscriptions/{username}.{format}`                    |

### Subscriptions (advanced / delta)

| Method | Path                                                  |
|--------|-------------------------------------------------------|
| POST   | `/api/2/subscriptions/{username}/{deviceid}.json`     |
| GET    | `/api/2/subscriptions/{username}/{deviceid}.json`     |

### Episode actions

| Method | Path                              |
|--------|-----------------------------------|
| POST   | `/api/2/episodes/{username}.json` |
| GET    | `/api/2/episodes/{username}.json` |

### Settings

| Method | Path                                          |
|--------|-----------------------------------------------|
| GET    | `/api/2/settings/{username}/{scope}.json`     |
| POST   | `/api/2/settings/{username}/{scope}.json`     |

`scope` is one of `account`, `device`, `podcast`, `episode`. The latter
three require the relevant query params (`device=...`, `podcast=...`,
`episode=...`).

### Favorites

| Method | Path                                 |
|--------|--------------------------------------|
| GET    | `/api/2/favorites/{username}.json`   |

### Podcast lists

| Method  | Path                                                   |
|---------|--------------------------------------------------------|
| GET     | `/api/2/lists/{username}.json`                         |
| POST    | `/api/2/lists/{username}/create.{format}?title=...`    |
| GET     | `/api/2/lists/{username}/list/{listname}.{format}`     |
| PUT     | `/api/2/lists/{username}/list/{listname}.{format}`     |
| DELETE  | `/api/2/lists/{username}/list/{listname}.{format}`     |

## Formats

`{format}` placeholders accept `json`, `xml`, `opml`, `txt`, `jsonp`.
For `jsonp`, supply `?jsonp=callback_name`.

## Authentication

HTTP Basic on every protected endpoint **or** the `sessionid` cookie
returned by `/api/2/auth/{username}/login.json`. The path-`{username}`
must equal the authenticated user; otherwise the server returns 400.
