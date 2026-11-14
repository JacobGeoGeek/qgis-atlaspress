# Local Development

## Configuration

Copy `config.example.json` to `config.json` and set the backend `baseUrl` and
`accessToken` under `supabase`. Supply a genuine access token for a dedicated
test user. Requests use this token as Bearer authorization.

This is temporary development configuration, not production login, session
storage, or token refresh. Never use a service-role key or commit real credentials.

`config.json` is ignored by Git, but the current `make package` target includes
it in the plugin ZIP. Do not share or publish an archive containing a real user
token. Git ignoring a file does not exclude it from packaging.

Configuration is loaded when the plugin starts. After changing the backend URL
or token, reload the plugin. The installed plugin reads its own `config.json`,
not the repository copy. Update that installed copy or rebuild and reinstall
the plugin before reloading. Missing or expired credentials display instructions
to update the installed configuration and reload the plugin.

## Preview Backend

The backend must support create, status, and retry under
`/functions/v1/mockups`. Local Printful testing requires a publicly accessible
source-image URL, such as an ngrok-backed storage URL.

## Automated Tests

Run tests with QGIS's Python environment:

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

## My Orders Verification

Use two genuine test-user sessions to check empty history, automatic pagination,
details, absent or expired previews, and request failures.

Load orders for user A, then reload the plugin with user B's credentials,
including while requests or preview downloads are pending. Verify that user A's
rows, details, and images are cleared and that delayed callbacks cannot restore
them. Changes to configuration are not watched while the plugin is running.

Reading existing history requires no Stripe payment or Printful confirmation.

Deploy the backend order filtering/sorting enhancement before using the updated
plugin. List requests send `sort=newest` or `sort=oldest` and optionally a stored
`status` value. Filtering and ordering apply to all matching orders on the server,
not only the loaded rows. Existing backend versions reject these new parameters;
the plugin displays that request failure rather than silently filtering locally.

Verify status/sort combinations across several pages, rapid selection changes,
Reset, and manual/automatic refresh. Back from details retains the selections;
closing and reopening My Orders restores the defaults. Check that an order whose
status leaves the selected filter disappears from the list but its open details
remain readable.

While My Orders is open, the visible list or detail view refreshes every 30
seconds. List refreshes re-read enough cursor pages to cover the loaded rows;
updates preserve selection and scroll position. Temporary refresh failures keep
existing information visible and retry on the next interval. Polling stops on
close, plugin unload, or HTTP 401. Status refreshes do not repeatedly download
previews or bypass their bounded retry action.
