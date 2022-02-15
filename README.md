# Quota Management

OpenShift application for easy management of resources for projects located within multiple clusters.

<p align="center">
  <img src="docs/example.png">
</p>

## In short

- This is a single go-to interface for creating projects and managing quota for these projects across multiple clusters
- ResourceQuota fields meant for editing are fully configurable and the application supports multiple ResourceQuota objects
- Full schema validation on client and server
- Clear distinction between development and production clusters
- Quota managers do not carry the RBAC permissions, the application itself performs the actions
- Each request is logged accordingly

## Deployment

1.  (Disconnected environment) Run `make disconnected-files` and transfer all the files in "./disconnected" directory to your environment
2.  Run `oc new-project <project-name>` to create a new project for the application. Make sure the project has enough quota:
    - 4 pods (2 for currently running instances, 2 for rolling updates)
    - 400m CPU (200m for currently running instances, 200m for rolling updates)
    - 256Mi Memory (128Mi for currently running instances, 128Mi for rolling updates)
3.  (Disconnected environment) Push the transfered image to the internal repository of the project / other reachable registry
4.  Process the application template like so:

    ``` bash
    oc process -o yaml -f deploy/quota-management-template.yaml \
        -p NAMESPACE=<project-name> \
        -p OAUTH_ENDPOINT=<cluster-oauth-endpoint (e.g. oauth-openshift.apps-crc.testing)> \
        -p ROUTER_CANONICAL_HOSTNAME=<router-subdomain (e.g. apps-crc.testing)> \
        -p IMAGE=<quota-management-image (only relevant for disconnected environments)>
        > quota-management.yaml
    ```

    Note: more parameters are available and can be viewed at the bottom of the template file

Before creating the application manifest, configure its behavior to match your environment using the Management step below.

## Management

Edit the resulting manifest using `vim quota-management.yaml` command. Objects of interest:

- OAuthClient: used to authenticate the user that accesses the application. Should not be edited.
- Group: users in this group are allowed to access the application, edit quota and create new projects. Add relevant users to the list (as they appear in the output of `oc get users`)
- ConfigMap (quota-scheme): this scheme tells the application which ResourceQuota objects and which fields within them can be edited.
  Here is how this dictionary works:

  - 1st level keys: ResourceQuota objects by that name that exist in the namespace
    - 2nd level keys: fields that are present in `.spec.hard` of their ResourceQuota object
        - __name__: display name for the current field
        - __units__: allowed units (Mi, Gi, etc.) for the current field. Can be blank (pods, pvcs), quota unit (Memory, Storage, CPU), or a list of quota units to choose from
        - __type__: data type for the current field (can only be "int" or "float")

  Quota Management assumes that these objects and fields within them are defined in the default project request template of each managed cluster.

- ConfigMap (ca-bundle): CA certificates that this application trusts
- Secret: clusters that Quota Management can manage. Each key in the secret represents a cluster and value for each key must be a dictionary with the following fields:

  - __displayName__: display name for the cluster
  - __api__: full API URL for the remote cluster (including "https://" and port)
  - __production__: boolean which tells the application whether the cluster is production
  - __token__: bearer token used to perform management on remote cluster

  In order to get the token, a service account with proper permissions must be created on that cluster. Run `oc create -f deploy/quota-management-serviceaccount.yaml` against the remote cluster to create it. Then retrieve the token using `oc sa get-token quota-manager -n default`.

- ServiceAccount: service account for application pods to run with
- ClusterRole: permissions to perform token reviews (to resolve the user name for the user accessing the application) and get a list of quota managers from the group.
- ClusterRoleBinding: grants permissions above to the application service account
- Deployment/Service/Route: the application itself. Generally should not be of interest

Now deploy the manifest: `oc create -f quota-management.yaml`
