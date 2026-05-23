// EKS_Upgrade_Prod
// Parameters (MODE, UPGRADE_TARGET, Target_Version, CLUSTER, EMAIL_TO)
// are configured in the Jenkins job UI — not defined here.

pipeline {
    agent { label 'HBA-Analytics' }

    environment {
        ENV = 'Prod'
    }

    stages {
        stage('Validate Parameters') {
            steps {
                script {
                    if (params.MODE == 'upgrade') {
                        if (!params.UPGRADE_TARGET || params.UPGRADE_TARGET == 'N/A') {
                            error('UPGRADE_TARGET is required for upgrade mode')
                        }
                        if (!params.CLUSTER?.trim()) {
                            error('CLUSTER is required for upgrade mode')
                        }
                        if (params.UPGRADE_TARGET in ['cluster', 'all'] && !params.Target_Version?.trim()) {
                            error('Target_Version is required when upgrading cluster or all')
                        }
                    }
                }
            }
        }

        stage('Discover') {
            when { expression { params.MODE == 'discover' } }
            steps {
                dir('eks-upgrade-automation') {
                    script {
                        def cmd = "python3 discover.py --env ${ENV}"
                        if (params.EMAIL_TO?.trim()) {
                            cmd += " --email-to ${params.EMAIL_TO.replace(',', ' ')}"
                        }
                        sh cmd
                    }
                }
            }
        }

        stage('Upgrade') {
            when { expression { params.MODE == 'upgrade' } }
            steps {
                dir('eks-upgrade-automation') {
                    script {
                        def cmd = "python3 upgrade.py --mode ${params.UPGRADE_TARGET} --cluster ${params.CLUSTER} --env ${ENV}"
                        if (params.UPGRADE_TARGET in ['cluster', 'all'] && params.Target_Version?.trim()) {
                            cmd += " --target-version ${params.Target_Version}"
                        }
                        sh cmd
                    }
                }
            }
        }

        stage('Validate') {
            when { expression { params.MODE == 'validate' } }
            steps {
                dir('eks-upgrade-automation') {
                    script {
                        def cmd = "python3 validate.py --env ${ENV}"
                        if (params.CLUSTER && params.CLUSTER != 'ALL') {
                            cmd += " --cluster ${params.CLUSTER}"
                        }
                        if (params.EMAIL_TO?.trim()) {
                            cmd += " --email-to ${params.EMAIL_TO.replace(',', ' ')}"
                        }
                        sh cmd
                    }
                }
            }
        }
    }

    post {
        success {
            script {
                if (params.EMAIL_TO?.trim()) {
                    emailext(
                        to: params.EMAIL_TO,
                        subject: "SUCCESS: EKS Prod ${params.MODE} - Build #${BUILD_NUMBER}",
                        body: """EKS Prod ${params.MODE} completed successfully.

Mode: ${params.MODE}
Cluster: ${params.CLUSTER ?: 'ALL'}
Build: ${BUILD_URL}""",
                    )
                }
            }
        }
        failure {
            script {
                if (params.EMAIL_TO?.trim()) {
                    emailext(
                        to: params.EMAIL_TO,
                        subject: "FAILURE: EKS Prod ${params.MODE} - Build #${BUILD_NUMBER}",
                        body: """EKS Prod ${params.MODE} failed.

Mode: ${params.MODE}
Cluster: ${params.CLUSTER ?: 'ALL'}
Build: ${BUILD_URL}

Check the console output for details.""",
                    )
                }
            }
        }
    }
}
