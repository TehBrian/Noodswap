pipeline {
  agent any

  parameters {
    string(name: 'DEPLOY_PATH', defaultValue: '/home/noodswap-user/noodswap', description: 'Absolute path to the deployment checkout on Ubuntu')
    string(name: 'IMAGE_REPOSITORY', defaultValue: 'ghcr.io/replace-me/noodswap', description: 'GHCR image repository without tag')
  }

  options {
    disableConcurrentBuilds()
    timestamps()
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Deploy Main') {
      when {
        branch 'main'
      }

      steps {
        withCredentials([
          usernamePassword(
            credentialsId: 'ghcr-readonly',
            usernameVariable: 'GHCR_USERNAME',
            passwordVariable: 'GHCR_TOKEN'
          )
        ]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail

            cd "${DEPLOY_PATH}"
            echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
            IMAGE_REPOSITORY="${IMAGE_REPOSITORY}" IMAGE_TAG=latest ./deploy/update.sh
            docker logout ghcr.io
          '''
        }
      }
    }
  }
}
