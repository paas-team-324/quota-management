
# Make sure that:
# * docker is running
# * Red Hat CRC is running
# * able to push to internal registry (make get-registry-certificate)

VERSION ?= 1.3
IMAGE ?= default-route-openshift-image-registry.apps-crc.testing/quota-management/quota-management

get-registry-certificate:
	oc get secret router-certs-default -n openshift-ingress -o jsonpath='{.data.tls\.crt}' | base64 -d

	#
	# Add the following certs to trusted CAs of your machine and restart docker service
	#
	# Alternatively, you can add it as insecure registry in /etc/docker/daemon.json like so:
	# {
	# 	"insecure-registries" : [ "default-route-openshift-image-registry.apps-crc.testing" ]
	# }
	#

build:
	docker build -t ${IMAGE}:${VERSION} .

push:
	docker push ${IMAGE}:${VERSION}

build-push: build push

disconnected-files:

	# pull and store image
	docker pull docker.io/paasteam324/quota-management:${VERSION}
	docker save docker.io/paasteam324/quota-management:${VERSION} -o /tmp/quota-management-${VERSION}.tar

	# set-up disconnected dir
	mkdir -p ./disconnected
	rm ./disconnected/* -rf

	# archive files
	7za a -v500m ./disconnected/quota-management-${VERSION}.7z \
		/tmp/quota-management-${VERSION}.tar \
		deploy/quota-management-serviceaccount.yaml \
		deploy/quota-management-template.yaml

	# remove stored image
	rm /tmp/quota-management-${VERSION}.tar -f
	docker rmi docker.io/paasteam324/quota-management:${VERSION}

	#
	# ==========================================================
	# Disconnected files available in "./disconnected" directory
	# ==========================================================
	#
