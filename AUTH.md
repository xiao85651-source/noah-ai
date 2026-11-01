# Noah member sign-in

The public app supports Google Identity Services using a dedicated Web client. The client ID is public configuration; this flow does not use an OAuth client secret. Set `NOAH_GOOGLE_CLIENT_ID` on the cloud edge and keep `public/auth-config.json` pointed at that edge's HTTPS origin. Without a configured ID the app reports that sign-in is unavailable.

The owner-approved existing Google project is `atomic-land-489614-v7`. Its login brand is Noah, with homepage `https://zenithsmart.xin/` and privacy notice `https://zenithsmart.xin/privacy.html`. Create a separate Noah Web client; retain the project's earlier client. Configure exact JavaScript origins for the public app. Branding is shared by clients in a Google project.

Only basic identity is used: Google subject, verified email and display name. No Gmail, Drive or contacts permission is requested. Google's official library checks the signature, audience, issuer and expiry. A single-use, ten-minute nonce prevents replay. Certificate downloads use a ten-second timeout and an in-memory cache.

Noah member sessions expire after one hour. The cloud retains only a hashed session token and basic profile in bounded memory; the browser retains the opaque token in the current tab's sessionStorage. Signing out revokes that session. Restarting or recycling the free cloud container signs users out. This pilot has no permanent account database or cross-device chat synchronization.

Every Google account receives the `member` role. Member tokens cannot authorize the owner console, training controls, exports or contribution ingress. Owner Basic authentication and contributor invitations remain independent. `ephemeral-test` continues to reject training writes; the only added POST routes are member sign-in and sign-out.

Default permitted member API origins are the primary domain and the two existing Noah Workers domains, plus the configured coordinator origin. `NOAH_AUTH_ORIGINS`, when supplied, replaces the default public list with a comma-separated exact allowlist. There is no wildcard credential CORS and no cookie-based member session.

The Ark introduction runs once per tab session, can be skipped or replayed, and respects reduced-motion preferences. It does not start training or obtain device resource consent.

Verification: `python -m unittest training.test_google_login -v` covers real RSA signature/audience/expiry checks using an ephemeral test key, session expiry and revocation, one-use nonces, origin restrictions and member/owner separation. Test injection exists only in Python constructors, with no environment bypass or public fake-login route.

References: [Google server verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [Google Web client configuration](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).
