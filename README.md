# Quota Management

OpenShift application for easy management of resources for projects located within multiple clusters.

<p align="center">
  <img src="docs/example.png">
</p>

## In short

- This is a single go-to interface for creating projects and managing quota for these projects across multiple clusters
- ResourceQuota fields meant for editing are fully configurable and there is support for multiple ResourceQuota objects
- Full schema validation on client and server
- Clear distinction between development and production clusters
- Quota managers do not carry the RBAC permissions, the application itself performs the actions
- Each request is logged accordingly
