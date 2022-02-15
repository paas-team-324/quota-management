
# Make sure that:
# * docker is running
# * Red Hat CRC is running

VERSION ?= 1.3

# TODO
trust-registry:
	echo Not implemented

build:
	docker build -t default-route-openshift-image-registry.apps-crc.testing/quota-management/quota-management:${VERSION} .

push: trust-registry
	docker push default-route-openshift-image-registry.apps-crc.testing/quota-management/quota-management:${VERSION}

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
