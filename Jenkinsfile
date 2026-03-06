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

  environment {
    DEPLOY_IMAGE_TAG = ''
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.DEPLOY_IMAGE_TAG = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
          echo "Resolved deploy image tag: ${env.DEPLOY_IMAGE_TAG}"
        }
      }
    }

    stage('Wait For Tagged Image') {
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

            image_ref="${IMAGE_REPOSITORY}:${DEPLOY_IMAGE_TAG}"
            echo "Waiting for image to become available: ${image_ref}"
            echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin

            max_attempts=30
            attempt=1
            until docker manifest inspect "$image_ref" >/dev/null 2>&1; do
              if [ "$attempt" -ge "$max_attempts" ]; then
                echo "Timed out waiting for ${image_ref}" >&2
                docker logout ghcr.io >/dev/null 2>&1 || true
                exit 1
              fi
              echo "Image not available yet (attempt ${attempt}/${max_attempts}); retrying in 10s..."
              attempt=$((attempt + 1))
              sleep 10
            done

            echo "Image available: ${image_ref}"
            docker logout ghcr.io
          '''
        }
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
            IMAGE_REPOSITORY="${IMAGE_REPOSITORY}" IMAGE_TAG="${DEPLOY_IMAGE_TAG}" ./deploy/update.sh
            docker logout ghcr.io
          '''
        }
      }
    }

    stage('Verify Running Image') {
      when {
        branch 'main'
      }

      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          expected_image="${IMAGE_REPOSITORY}:${DEPLOY_IMAGE_TAG}"
          container_name="noodswap-bot"

          # Ensure the container is currently running.
          if ! docker ps --filter "name=^/${container_name}$" --filter "status=running" --quiet | grep -q .; then
            echo "Container ${container_name} is not running after deploy" >&2
            docker ps -a --filter "name=^/${container_name}$"
            exit 1
          fi

          actual_image=$(docker inspect --format '{{.Config.Image}}' "${container_name}")
          echo "Expected image: ${expected_image}"
          echo "Running image:  ${actual_image}"

          if [ "${actual_image}" != "${expected_image}" ]; then
            echo "Deployed container image does not match expected commit tag" >&2
            exit 1
          fi

          echo "Running image tag matches expected commit tag."
        '''
      }
    }
  }
}
