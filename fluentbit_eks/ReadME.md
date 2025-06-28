Fluent-bit Opensearch with OIDC cross-account connection


Steps:


1. Get oidc of cluster: 

* switch to your account and run : 
	aws eks list-clusters;
	export MY_CLUSTER=<your_eks_cluster_name>

	aws eks describe-cluster --name $MY_CLUSTER --query "cluster.identity.oidc.issuer" --output text
	e.g:
		aws eks describe-cluster --name <eks_cluster_name> --query "cluster.identity.oidc.issuer" --output text
		

* List the IAM OIDC providers in your account. Replace EXAMPLED539D4633E53DE1B71EXAMPLE with the value returned from the previous command.
		aws iam list-open-id-connect-providers | grep EXAMPLED539D4633E53DE1B71EXAMPLE
		o/p: "Arn": "arn:aws:iam::851853320826:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/78269F5017CD4455C213E4DA2EED61D9"


* If output is returned from the previous command, then you already have a provider for your cluster. If no output is returned, then you must create an IAM OIDC provider.

* Create an IAM OIDC identity provider for your cluster with the following command. Replace my-cluster with your own value.
	eksctl utils associate-iam-oidc-provider --cluster $MY_CLUSTER --approve

For refrence: https://docs.aws.amazon.com/eks/latest/userguide/enable-iam-roles-for-service-accounts.html



2. Add identity providers in logging account where opensearch is configured:
 
* Open the IAM console at https://console.aws.amazon.com/iam/.

* In the navigation pane, choose Identity providers, and then choose Add provider.

* For Configure provider, choose OpenID Connect.

* For Provider URL, type the URL of the IdP which is obtained from the output of step 1 first command command

		e.g. https://oidc.eks.us-east-1.amazonaws.com/id/78269F5017CD4455C213E4DA2EED61D9

* Choose Get thumbprint to verify the server certificate of your IdP.

* For Audience, use "sts.amazonaws.com"

* Verify the information that you have provided. When you are done choose Add provider.


For Refrence: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html


3. Add trust relationship for already created role "rol_bundles_opensearch_access":

* Go to role and search "rol_bundles_opensearch_access"
* Click "Trust Relationships" and edit trust policy.
* Add new statement in statement block with below values.

{
			"Sid": "<YOUR_ACCOUNT_NAME>",
			"Effect": "Allow",
			"Principal": {
				"Federated": "arn:aws:iam::<account_id>>:oidc-provider/<OIDC_VALUE_OBTAINED_IN_STEP_1_OR_ADDED_IN_STEP_2>"
			},
			"Action": "sts:AssumeRoleWithWebIdentity",
			"Condition": {
				"StringEquals": {
					"oidc.eks.us-east-1.amazonaws.com/id/<id>:sub": "system:serviceaccount:<namespace>:<service_account>"
				}
			}
		}

* Save it.

4. Apply the fluent-bit yaml:

* Switch to account where cluster reside.

* Before applying yaml, please change "Logstash_Prefix_Key $kubernetes['container_name']" in config as per your condition for the indexing.
    For example: 
    If application is using: Logstash_Prefix_Key $kubernetes['container_name'] which will create indices based on the container name.
    If application is using: Logstash_Prefix_Key $kubernetes['namespace_name'] which will create indices base on namespace.

* Apply fluentbit.yaml
		kubectl apply -f fluentbit.yaml


### NOTE: In recent change, “Logstash_DateFormat %Y.%m” is added in output for the indexing based on container_name.%Y.%m .###
