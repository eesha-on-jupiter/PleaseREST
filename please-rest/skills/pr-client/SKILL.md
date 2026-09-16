---
name: pr-client
description: API client file structure and HTTP rules for Grasshopper REST API plugins
---

# Skill: API client

For the single [PluginName]Client.cs file in Utilities/.
This is the only file that touches HttpClient.

---

## Organisation

```
#region Constructor and setup
#region [Primary resource] methods
#region [Secondary resource] methods
#region [Additional groups as needed]
#region Private helpers
```

---

## Pattern

```csharp
using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace [PluginName]
{
    public sealed class [PluginName]Client
    {
        #region Constructor and setup

        // ONE HttpClient for the whole plugin — shared across every component and every solve.
        // A per-solve HttpClient exhausts sockets and ignores DNS changes; a per-solve wrapper
        // around a shared client is the correct shape. BaseAddress MUST end with '/'.
        private static readonly HttpClient _http = new HttpClient
        {
            BaseAddress = new Uri("[base url]/"),          // e.g. "https://api.example.com/v1/"
            Timeout = TimeSpan.FromSeconds(30)             // SolveInstance blocks for at most this long
        };

        // How the token travels — from the entry's auth_in in call-library-validated.json:
        //   "header"          → Authorization: Bearer <token>            (default)
        //   "header:<Name>"   → <Name>: <token>                          (raw API key header)
        //   "query:<param>"   → ?<param>=<token>                          (token in query string)
        private const string AuthIn = "[auth_in from call-library-validated.json]";

        private readonly string _token;

        public [PluginName]Client(string token)
        {
            _token = (token ?? "").Trim();
        }

        // relativeUrl NEVER starts with '/': with BaseAddress ".../v1/", a leading slash makes
        // .NET drop the "/v1" path segment and request the origin root (silent 404s).
        private HttpRequestMessage NewRequest(HttpMethod method, string relativeUrl)
        {
            relativeUrl = (relativeUrl ?? "").TrimStart('/');
            var req = new HttpRequestMessage(method, ApplyQueryAuth(relativeUrl));
            ApplyAuth(req);
            // add any additional required headers here (feasibility.json extra_headers)
            return req;
        }

        private void ApplyAuth(HttpRequestMessage req)
        {
            if (AuthIn.StartsWith("query:")) return;                     // handled in the URL
            if (AuthIn.StartsWith("header:"))
            {
                req.Headers.TryAddWithoutValidation(AuthIn.Substring("header:".Length), _token);
                return;
            }
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _token);
        }

        private string ApplyQueryAuth(string relativeUrl)
        {
            if (!AuthIn.StartsWith("query:")) return relativeUrl;
            string param = AuthIn.Substring("query:".Length);
            string sep = relativeUrl.Contains("?") ? "&" : "?";
            return relativeUrl + sep + Uri.EscapeDataString(param) + "=" + Uri.EscapeDataString(_token);
        }

        // Every path segment and query value goes through this — never string-concatenate raw input
        private static string Esc(string value) => Uri.EscapeDataString(value ?? "");

        #endregion

        #region [Resource] methods

        public async Task<Tuple<bool, string, string>> [Action]Async([params])
        {
            try
            {
                if (string.IsNullOrWhiteSpace([requiredParam])) return Fail("[param] is empty.");

                // url_template "/boards/{board_id}/items?limit={limit}" becomes:
                var req = NewRequest(HttpMethod.Get, "boards/" + Esc(boardId) + "/items?limit=" + Esc(limit));
                return await SendAsync(req).ConfigureAwait(false);
            }
            catch (Exception ex) { return Fail(ex.ToString()); }
        }

        // POST/PUT/PATCH: body is the JSON string a builder produced (pr-builders) — never rebuilt here
        public async Task<Tuple<bool, string, string>> Create[Thing]Async(string payloadJson)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(payloadJson)) return Fail("[Thing] JSON is empty.");

                var req = NewRequest(HttpMethod.Post, "[endpoint]");
                req.Content = new StringContent(payloadJson, Encoding.UTF8, "application/json");
                return await SendAsync(req).ConfigureAwait(false);
            }
            catch (Exception ex) { return Fail(ex.ToString()); }
        }

        #endregion

        #region Private helpers

        // Single send path: 429 backoff (honours Retry-After, max 3 retries), 401 surfaced as
        // "token expired / invalid", every other non-2xx returned with the body for diagnosis
        private async Task<Tuple<bool, string, string>> SendAsync(HttpRequestMessage template)
        {
            for (int attempt = 0; ; attempt++)
            {
                int status; string reason; string body; TimeSpan? retryAfter;

                // The template is never sent — each attempt sends a fresh clone, because
                // HttpClient on net48 disposes the request content after the first send.
                using (var req = await CloneAsync(template).ConfigureAwait(false))
                using (var res = await _http.SendAsync(req).ConfigureAwait(false))
                {
                    status     = (int)res.StatusCode;
                    reason     = res.ReasonPhrase;
                    body       = await res.Content.ReadAsStringAsync().ConfigureAwait(false);
                    retryAfter = res.Headers.RetryAfter?.Delta;
                }

                if (status == 429 && attempt < 3)
                {
                    var delay = retryAfter ?? TimeSpan.FromSeconds(Math.Pow(2, attempt));
                    if (delay > TimeSpan.FromSeconds(30)) delay = TimeSpan.FromSeconds(30);
                    await Task.Delay(delay).ConfigureAwait(false);
                    continue;
                }

                if (status == 401)
                    return Fail("HTTP 401 — token expired or invalid. Get a fresh token and re-run.\n" + body);

                if (status < 200 || status > 299)
                    return Fail("HTTP " + status + " " + reason + "\n" + body);

                return Ok(body);
            }
        }

        // HttpRequestMessage can only be sent once — always send a clone of the template
        private static async Task<HttpRequestMessage> CloneAsync(HttpRequestMessage req)
        {
            var clone = new HttpRequestMessage(req.Method, req.RequestUri);
            foreach (var h in req.Headers) clone.Headers.TryAddWithoutValidation(h.Key, h.Value);
            if (req.Content != null)
            {
                string body = await req.Content.ReadAsStringAsync().ConfigureAwait(false);
                clone.Content = new StringContent(body, Encoding.UTF8,
                    req.Content.Headers.ContentType?.MediaType ?? "application/json");
            }
            return clone;
        }

        private static Tuple<bool, string, string> Ok(string body)
            => new Tuple<bool, string, string>(true, body, "");

        private static Tuple<bool, string, string> Fail(string error)
            => new Tuple<bool, string, string>(false, "", error);

        #endregion
    }
}
```

Rules:
- **Build every method FROM `spec/call-library-validated.json` — never hand-write from docs.** Each
  public method maps to one validated entry by `endpoint_id`; take the method, `url_template`,
  headers, and body shape from that entry. If `call-library-validated.json` does not exist, STOP and
  run Phases 6–7 (pr-api-extractor → pr-api-tester) first. The client is the consumer of the MCP output;
  skipping the MCPs and writing calls from the docs is a pipeline violation (dogfood: MCPs were
  silently bypassed this way).
- **PATCH on net48:** `HttpMethod.Patch` does not exist in .NET Framework 4.8 (Rhino 7 target). Use
  `new HttpMethod("PATCH")` for PATCH and any verb beyond GET/POST/PUT/DELETE/HEAD. (dogfood F5)
- `using System.Net.Http;` is required; the net48 target also needs the `System.Net.Http` reference
  in the `.csproj` (handled by `pr-vs-project`). (dogfood F3)
- **`HttpClient` is `private static readonly` — one per plugin, shared by every component and every
  solve.** The wrapper class is constructed per solve (cheap: it only holds the token); the socket
  pool is not. Never `new HttpClient()` per call or per component
- **`Timeout = 30 s`** always set — the default 100 s blocks the Rhino UI thread for the whole call
- **`BaseAddress` ends with `/`; every `relativeUrl` starts without `/`.** If `base_url` carries a
  path (`https://slides.googleapis.com/v1`), a leading-slash relative URL makes .NET discard that path
  and hit the origin root — a silent 404. `NewRequest` trims the slash defensively; still write them
  without it
- **Every path segment and query value goes through `Uri.EscapeDataString`** (`Esc()` helper) —
  names with spaces, `q=name contains '…'` filters, slashes in IDs all break otherwise
- **All auth goes through `ApplyAuth` / `ApplyQueryAuth`, driven by the entry's `auth_in`** from
  `call-library-validated.json`: `"header"` (Bearer, default), `"header:<Name>"` (raw key header),
  `"query:<param>"` (token in the query string). Never set an auth header inline in a method. If
  entries disagree on `auth_in`, use a per-method override, not a second client
- All sends go through the single `SendAsync` helper — 429 backoff (honours `Retry-After`, capped at
  30 s, max 3 retries), 401 surfaced as "token expired or invalid", other non-2xx returned with body
- Every public method returns `Tuple<bool, string, string>` — (success, result, error)
- `Ok()` and `Fail()` are private static helpers — never inline the tuple
- All public methods are `async Task<...>` with `ConfigureAwait(false)` on every await — no sync
  wrappers here; the **component** bridges sync→async with `Task.Run(...).GetAwaiter().GetResult()`
  (see `pr-component` "Calling the client")
- Guard clauses at top of every method before any HTTP call
- XML `<summary>` only on non-obvious methods — skip straightforward CRUD
- Rate limit delays inside pagination loops only: `await Task.Delay(350)`; bulk-write pacing also
  lives here (see `pr-bulk-data`) — never in a component
- Components never call `HttpClient` directly — always through this client

## Auth methods — what the client does and does not do

- **Bearer / API-key tokens**: supported via `auth_in` above. The token is a component input (`Token`
  / `T`) — it is never stored by the client
- **OAuth2 access tokens (Google etc.) expire** — typically after 1 hour. This client does **not**
  refresh them: there is no refresh-token flow and no client secret in a Grasshopper plugin. A 401
  therefore comes back as `Fail("HTTP 401 — token expired or invalid…")` so the component's `Status`
  output tells the user to paste a fresh token. Document that in `pr-docs` `authentication.md`
- **Basic auth**: not generated by default; if the API needs it, `ApplyAuth` sets
  `Authorization: Basic <base64>` — keep it inside `ApplyAuth`
