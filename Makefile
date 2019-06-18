.PHONY: clean test sdist all docker test

all: test sdist

clean:
	rm -rf `find . | grep \.pyc`
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info

test:
	@python setup.py test 

sdist:
	@python setup.py sdist

docker: clean sdist
	@docker build --rm=true --force-rm=true -t csirtgadgets/zyre -f Dockerfile .

docker-test:
	@docker run -it --rm --name zyre-test -p 4444:49154 -p 4445:49155 csirtgadgets/zyre:latest
