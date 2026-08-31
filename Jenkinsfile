// Jenkinsfile
//
// This is our Continuous Deployment (CD) pipeline. Jenkins runs this to deploy
// our already-built Docker images (built and pushed by GitHub Actions to
// Docker Hub) onto a local Kubernetes cluster (Minikube, K3s, or MicroK8s).
//
// Stages, in plain English:
//   1. Say hello on Slack (deployment started)
//   2. Connect to the Kubernetes cluster using a saved kubeconfig file
//   3. Roll out the new image tag to every Deployment, one at a time
//   4. Wait and confirm each rollout finished healthy
//   5. Report success on Slack - or automatically roll back and report failure
//
// SECURITY NOTE: This file does NOT contain the real Slack webhook URL or the
// real kubeconfig file. Both are pulled in at runtime from Jenkins' own
// Credentials store, so nothing sensitive ever gets committed to Git.
// See README.md for exact step-by-step setup instructions.

pipeline {
    agent any   // Run this pipeline on any available Jenkins agent/machine

    // A build parameter lets you optionally pass in the exact Docker image
    // tag (e.g. a Git commit SHA) that GitHub Actions built and pushed.
    // Leave it blank to just deploy whatever Git commit triggered this build.
    parameters {
        string(name: 'IMAGE_TAG', defaultValue: '', description: 'Docker Hub image tag to deploy (leave blank to use the current Git commit SHA)')
    }

    // ------------------------------------------------------------
    // Variables used throughout the pipeline
    // ------------------------------------------------------------
    environment {
        // The Docker Hub username where GitHub Actions pushed our images.
        // Change this to your own Docker Hub username.
        DOCKERHUB_USERNAME = 'melishaadh'

        // Pulled in from Jenkins Credentials (kind: Secret Text) - keeps the
        // real Slack URL out of this file and out of Git history.
        SLACK_WEBHOOK_URL = credentials('slack-webhook-url')

        // The Kubernetes namespace all our resources live in (see k8s/postgres-pv-pvc-secret.yaml)
        K8S_NAMESPACE = 'calcu'

        // The Deployments we need to update, space-separated. The nginx gateway
        // is not listed: its image tag is ":latest" and its routing config is
        // baked in, so it does not participate in tag-based rollouts.
        SERVICES = 'scientific-engine financial-engine history-service frontend'
    }

    options {
        timestamps()                                  // Prefix every log line with a timestamp
        disableConcurrentBuilds()                      // Never run two deployments at the same time
        buildDiscarder(logRotator(numToKeepStr: '20'))  // Only keep the last 20 build logs
    }

    stages {

        // ------------------------------------------------------------
        // STAGE 1: Get the latest code
        // ------------------------------------------------------------
        stage('Checkout Code') {
            steps {
                checkout scm   // "scm" means: check out whatever branch/repo triggered this build
                script {
                    // Resolve the deploy tag ONLY after checkout, when
                    // env.GIT_COMMIT is populated. Priority:
                    //   1. the IMAGE_TAG build parameter, if given
                    //   2. the exact commit SHA that triggered this build
                    //   3. "latest" as a last resort
                    def param = params.IMAGE_TAG?.trim()
                    env.DEPLOY_TAG = param ? param : (env.GIT_COMMIT ?: 'latest')
                    echo "Deploying image tag: ${env.DEPLOY_TAG}"
                }
            }
        }

        // ------------------------------------------------------------
        // STAGE 2: Let the team know a deployment is starting
        // ------------------------------------------------------------
        stage('Notify: Start') {
            steps {
                slackNotify(
                    ":rocket: Deployment STARTED for calcu - tag `${env.DEPLOY_TAG}` - build #${BUILD_NUMBER}",
                    '#439FE0'
                )
            }
        }

        // ------------------------------------------------------------
        // STAGE 3: Connect to our local Kubernetes cluster
        // ------------------------------------------------------------
        stage('Connect to Kubernetes') {
            steps {
                // "kubeconfig-calcu" is a Jenkins Credential (kind: Secret file) containing
                // the kubeconfig file for your local cluster (Minikube/K3s/MicroK8s).
                // Setting KUBECONFIG tells every "kubectl" command below which cluster to talk to.
                withCredentials([file(credentialsId: 'kubeconfig-calcu', variable: 'KUBECONFIG')]) {
                    sh 'kubectl get nodes'   // Simple check to confirm we can talk to the cluster
                }
            }
        }

        // ------------------------------------------------------------
        // STAGE 4: Update the image tag on every Deployment (rolling update)
        // ------------------------------------------------------------
        stage('Deploy: Rolling Update') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-calcu', variable: 'KUBECONFIG')]) {
                    script {
                        slackNotify(":arrows_counterclockwise: Rolling update in progress for tag `${env.DEPLOY_TAG}`", '#439FE0')
                        def services = env.SERVICES.split(' ')
                        for (svc in services) {
                            // "kubectl set image" swaps the container image for a running Deployment.
                            // Kubernetes then automatically starts new pods and retires old ones
                            // gradually - this is the "rolling" part of a rolling update.
                            sh """
                                kubectl set image deployment/${svc} ${svc}=${DOCKERHUB_USERNAME}/calcu-${svc}:${env.DEPLOY_TAG} \
                                    --namespace=${K8S_NAMESPACE}
                            """
                        }
                    }
                }
            }
        }

        // ------------------------------------------------------------
        // STAGE 5: Wait for every rollout to finish and confirm it's healthy
        // ------------------------------------------------------------
        stage('Verify Rollout Health') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-calcu', variable: 'KUBECONFIG')]) {
                    script {
                        def services = env.SERVICES.split(' ')
                        for (svc in services) {
                            // "rollout status" waits and watches until all new pods pass their
                            // readiness probes. returnStatus:true lets us handle a failure
                            // ourselves instead of stopping the whole pipeline immediately.
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
    }

    // ------------------------------------------------------------
    // These blocks run automatically at the end, based on the final result
    // ------------------------------------------------------------
    post {
        success {
            slackNotify(":white_check_mark: Deployment SUCCESS for calcu - tag `${env.DEPLOY_TAG}` - build #${BUILD_NUMBER}", 'good')
        }
        failure {
            script {
                slackNotify(":x: Deployment FAILED for calcu - tag `${env.DEPLOY_TAG}` - rolling back automatically", 'danger')
                // "rollout undo" reverts every Deployment back to its previous working image,
                // so a bad deploy doesn't leave the app broken for users.
                withCredentials([file(credentialsId: 'kubeconfig-calcu', variable: 'KUBECONFIG')]) {
                    def services = env.SERVICES.split(' ')
                    for (svc in services) {
                        sh(script: "kubectl rollout undo deployment/${svc} --namespace=${K8S_NAMESPACE}", returnStatus: true)
                    }
                }
                slackNotify(":leftwards_arrow_with_hook: Rollback completed for calcu - build #${BUILD_NUMBER}", 'warning')
            }
        }
        always {
            cleanWs()   // Clean up the Jenkins workspace so the next build starts fresh
        }
    }
}

// Small helper function used by every stage above to post a formatted
// message to Slack. "|| true" keeps a Slack outage from failing the build.
def slackNotify(String message, String color) {
    sh """
        curl -sf -X POST -H 'Content-type: application/json' \
            --data '{"attachments":[{"color":"${color}","text":"${message}"}]}' \
            "\$SLACK_WEBHOOK_URL" || true
    """
}
