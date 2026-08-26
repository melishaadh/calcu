pipeline {
    agent any

    parameters {
        string(name: 'IMAGE_TAG', defaultValue: '', description: 'Git SHA / image tag produced by CI to deploy')
    }

    environment {
        AWS_REGION       = 'us-east-1'
        EKS_CLUSTER_NAME = 'calcu-eks-cluster'
        ECR_REGISTRY     = credentials('ecr-registry-url')
        AWS_CREDS        = credentials('aws-cli-credentials')
        SLACK_WEBHOOK_URL = credentials('slack-webhook-url')
        K8S_NAMESPACE    = 'calcu'
        SERVICES         = 'scientific-engine financial-engine history-service frontend'
        DEPLOY_TAG       = "${params.IMAGE_TAG ?: env.GIT_COMMIT}"
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('Notify: Start') {
            steps {
                slackNotify(
                    ":rocket: Deployment STARTED for calcu — tag `${DEPLOY_TAG}` — build #${BUILD_NUMBER}",
                    '#439FE0'
                )
            }
        }

        stage('AWS Authentication') {
            steps {
                sh '''
                    aws configure set aws_access_key_id "$AWS_CREDS_USR"
                    aws configure set aws_secret_access_key "$AWS_CREDS_PSW"
                    aws configure set region "$AWS_REGION"
                    aws sts get-caller-identity
                '''
            }
        }

        stage('Configure kubectl for EKS') {
            steps {
                sh '''
                    aws eks update-kubeconfig --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION"
                    kubectl get nodes
                '''
            }
        }

        stage('Deploy: Rolling Update') {
            steps {
                script {
                    slackNotify(":arrows_counterclockwise: Rolling update in progress for tag `${DEPLOY_TAG}`", '#439FE0')
                    def services = env.SERVICES.split(' ')
                    for (svc in services) {
                        sh """
                            kubectl set image deployment/${svc} ${svc}=${ECR_REGISTRY}/melishaadh/calcu-${svc}:${DEPLOY_TAG} \
                                --namespace=${K8S_NAMESPACE} --record
                        """
                    }
                }
            }
        }

        stage('Verify Rollout Health') {
            steps {
                script {
                    def services = env.SERVICES.split(' ')
                    for (svc in services) {
                        def status = sh(
                            script: "kubectl rollout status deployment/${svc} --namespace=${K8S_NAMESPACE} --timeout=180s",
                            returnStatus: true
                        )
                        if (status != 0) {
                            error("Rollout failed health checks for deployment/${svc}")
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            slackNotify(":white_check_mark: Deployment SUCCESS for calcu — tag `${DEPLOY_TAG}` — build #${BUILD_NUMBER}", 'good')
        }
        failure {
            script {
                slackNotify(":x: Deployment FAILED for calcu — tag `${DEPLOY_TAG}` — initiating automated rollback", 'danger')
                def services = env.SERVICES.split(' ')
                for (svc in services) {
                    sh(script: "kubectl rollout undo deployment/${svc} --namespace=${K8S_NAMESPACE}", returnStatus: true)
                }
                slackNotify(":leftwards_arrow_with_hook: Rollback completed for calcu — build #${BUILD_NUMBER}", 'warning')
            }
        }
        always {
            cleanWs()
        }
    }
}

def slackNotify(String message, String color) {
    sh """
        curl -sf -X POST -H 'Content-type: application/json' \
            --data '{"attachments":[{"color":"${color}","text":"${message}"}]}' \
            "\$SLACK_WEBHOOK_URL" || true
    """
}
