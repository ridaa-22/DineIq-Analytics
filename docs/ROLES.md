# Roles

| Role | Analytics | Scoped to assigned locations | Manage users/locations | Edit menu/promotions |
| --- | --- | --- | --- | --- |
| ADMIN | Yes | No | Yes | Yes |
| MANAGER | Yes | No | No | Yes |
| REGIONAL_MANAGER | Yes | Yes | No | No |
| ANALYST | Yes | No | No | No |

Checks occur in FastAPI. Unauthenticated API requests return 401; forbidden role or out-of-region requests return 403. Public registration grants only ANALYST. Admin creates or changes other roles. Existing local users migrate to ANALYST. JWTs expire after one hour. Set `DINEIQ_JWT_SECRET` in a deployment; local development creates a random secret in ignored `data/.jwt_secret`.
