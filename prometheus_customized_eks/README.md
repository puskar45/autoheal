MS-Teams Installation:

# helm repo add prometheus-msteams https://prometheus-msteams.github.io/helm-chart
# helm show values prometheus-msteams/prometheus-msteams > values.teams.yaml

In the values file, 

    > add webhook url of teams under connectors field and apply. Webhook url can be found under teams channel settings.
    > enable service monitor and add aditional args( enable -debug flag)
    # helm install prometheus-msteams prometheus-msteams/prometheus-msteams -f values.teams.yaml  -n monitoring --create-namespace
--------------------------------------

Prometheus-Stack:
# helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
# helm repo update

To get values file:
# helm show values prometheus-community/kube-prometheus-stack > values.prom.yaml
We need to modify this value file to satisfy our requirements:

    1. grafana has been disabled, set the value of enabled to false(as grafana is hosted on centralized ec2 serevr)

    2. retention of prometheus metric has been set to 60 days for nonprod/ 180 days for prod(see retention field under prometheusspec section) .

    3. For persistence of prometheus metrics and alertmanager data, ebs volume has been provisioned using storageclass and referenced in the values file under prometheus and alertmanager spec(see volumeclaimtemplate field under prometheusSpec and alertmanager Spec). 
        > kubectl apply -f storageclass_alertmanager.yaml -n monitoring
        > kubectl apply -f storageclass_prom_metrics.yaml -n monitoring
        To provision ebs volume, the ebs csi driver addon should be installed in eks cluster
    
    4. Set alertmanager config as required, in the values file we have added config for ms-teams and pagerduty. Set integration key of pagerduty and other configs.

    5. Since we will be creating our custom alertrules, we need to disable the creation of some of default alert rules. 
        Set false to rules that are not required.(See defaultrules field)

    6. Add a label of cluster in prometheus values file under externalLabels section:   
        cluster: <eks_cluster_name>
        This lable will be visible in alerts.

    7. Now install the helm chart using the customized values file:
        # helm install prometheus-stack prometheus-community/kube-prometheus-stack -f values.prom.yaml -n monitoring

    8. Finally apply your custom prometheus rule crd:
        Before applying, see labels and annotaions of this crd, since this is our custom rule file, for it to be managed by prometheus stack, labels and annotations shoud be set accordingly.
        # kubectl apply -f prometheusrules.yaml -n monitoring
        this will create a promtheus rules crd and immediately a configmap will also be created.

Verification:
    1. See all the pods are created except for grafana
    2. See all PVCs are bounded(for prometheus metrics and alertmanager)
    3. See prometheus-operator alb in aws(and also check metrics in grafana)
    4. Send one test alert
---------------------------------
    On a cluster basis, you need to change 
        1. externallabels on prometheus spec
        2. Set differen metric retention days  for prod and nonprod cluster
        2. teams webhook url
        3. pager duty integration key
        4. apply storageclass manifest(use different annotationg for auto mode and standard mode cluster)
        5. Need to adjust prometheus rules(set warning or info label for nonprod and critical for prod cluster)


if you want to increase size of PVC, you cannot change it through helm upgarde as k8s does not allow resizxing of PVC of statefulset, You have to manually increase size of PVC, but also store this change in helm values file. After resizing PVC manually, ebs volume gets increased automatically, and the size of PVC also gets increased and the size fo the filesystem inside the container is also resized. Please manually verify volume resizing.

