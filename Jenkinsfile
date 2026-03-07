pipeline {
  agent any

  parameters {
    string(name: 'DEPLOY_PATH', defaultValue: '/home/noodswap-user/noodswap', description: 'Absolute path to the deployment checkout on Ubuntu')
    string(name: 'IMAGE_REPOSITORY', defaultValue: 'ghcr.io/tehbrian/noodswap', description: 'GHCR image repository without tag')
    string(name: 'DEPLOY_AS_USER', defaultValue: 'noodswap-user', description: 'Linux user to execute deploy/update.sh as (blank = current Jenkins user)')
  }

  options {
    disableConcurrentBuilds()
    timestamps()
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          String resolvedTag = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
          if (!resolvedTag || resolvedTag == 'null') {
            error('Failed to resolve deploy image tag from git rev-parse HEAD.')
          }
          echo "Resolved deploy image tag: ${resolvedTag}"
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

            deploy_image_tag="$(git rev-parse HEAD | tr -d '\n')"
            if [ -z "${deploy_image_tag}" ] || [ "${deploy_image_tag}" = "null" ]; then
              echo "Failed to resolve deploy image tag from git in Wait For Tagged Image stage." >&2
              exit 1
            fi

            docker_config_dir="$(mktemp -d)"
            cleanup() {
              docker --config "${docker_config_dir}" logout ghcr.io >/dev/null 2>&1 || true
              rm -rf "${docker_config_dir}"
            }
            trap cleanup EXIT

            image_ref="${IMAGE_REPOSITORY}:${deploy_image_tag}"
            echo "Waiting for image to become available: ${image_ref}"
            echo "$GHCR_TOKEN" | docker --config "${docker_config_dir}" login ghcr.io -u "$GHCR_USERNAME" --password-stdin

            max_attempts=30
            attempt=1
            until docker --config "${docker_config_dir}" manifest inspect "$image_ref" >/dev/null 2>&1; do
              if [ "$attempt" -ge "$max_attempts" ]; then
                echo "Timed out waiting for ${image_ref}" >&2
                exit 1
              fi
              echo "Image not available yet (attempt ${attempt}/${max_attempts}); retrying in 10s..."
              attempt=$((attempt + 1))
              sleep 10
            done

            echo "Image available: ${image_ref}"
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

            deploy_image_tag="$(git rev-parse HEAD | tr -d '\n')"
            if [ -z "${deploy_image_tag}" ] || [ "${deploy_image_tag}" = "null" ]; then
              echo "Failed to resolve deploy image tag from git in Deploy Main stage." >&2
              exit 1
            fi

            deploy_script="${DEPLOY_PATH}/deploy/update.sh"
            if [ ! -x "${deploy_script}" ]; then
              echo "Deploy script missing or not executable: ${deploy_script}" >&2
              exit 1
            fi

            deploy_user="${DEPLOY_AS_USER:-}"
            current_user="$(id -un)"
            if [ -n "${deploy_user}" ] && [ "${deploy_user}" != "${current_user}" ]; then
              if ! command -v sudo >/dev/null 2>&1; then
                echo "sudo is required to run deploy as ${deploy_user}, but sudo is not installed." >&2
                exit 1
              fi

              # Run the exact deploy script command permitted by sudoers.
              if ! sudo -n -u "${deploy_user}" IMAGE_REPOSITORY="${IMAGE_REPOSITORY}" IMAGE_TAG="${deploy_image_tag}" "${deploy_script}"; then
                echo "Deploy via sudo failed. Ensure Jenkins has NOPASSWD sudo for ${deploy_script} as ${deploy_user}." >&2
                echo "If GHCR is private, run one-time docker login as ${deploy_user} on the host." >&2
                exit 1
              fi
            else
              docker_config_dir="$(mktemp -d)"
              cleanup() {
                docker --config "${docker_config_dir}" logout ghcr.io >/dev/null 2>&1 || true
                rm -rf "${docker_config_dir}"
              }
              trap cleanup EXIT

              echo "$GHCR_TOKEN" | docker --config "${docker_config_dir}" login ghcr.io -u "$GHCR_USERNAME" --password-stdin
              DOCKER_CONFIG="${docker_config_dir}" IMAGE_REPOSITORY="${IMAGE_REPOSITORY}" IMAGE_TAG="${deploy_image_tag}" "${deploy_script}"
            fi
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

          deploy_image_tag="$(git rev-parse HEAD | tr -d '\n')"
          if [ -z "${deploy_image_tag}" ] || [ "${deploy_image_tag}" = "null" ]; then
            echo "Failed to resolve deploy image tag from git in Verify Running Image stage." >&2
            exit 1
          fi

          expected_image="${IMAGE_REPOSITORY}:${deploy_image_tag}"
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
