## flameTimewarpML

Readme for version 0.4.4 and earlier: [Readme v0.4.4](https://github.com/talosh/flameTimewarpML/blob/main/README_v044.md)

### Current status

* Training script and Flownet4 tested in production on Linux with constant speed retime
* Flownet2 tested on MacOS Apple Silicon with Pytorch 2.2.2

### Todo for v0.4.5 dev 001

* (done) ~~Add generalization logic to training script~~ 
* Refine batch retime script
* Share pre-trained weights for Flownet4 to enable using it in prod with command line.
* Optimize memory usage for Flownet4
* Add Fluidmorph and Interpolate logic to new Flame script.
* Add "Allow paint-in" switch for inference.

### Installing and configuring python environment manually

* pre-configured miniconda environment should be placed into hidden "packages/.miniconda" folder
* the folder is hidden (starts with ".") in order to keep Flame from scanning it looking for python hooks
* pre-configured python environment usually packed with release tar file

* download Miniconda for Mac or Linux (I'm using python 3.11 for tests) from 
<https://docs.anaconda.com/free/miniconda/miniconda-other-installer-links/>

* install downloaded Miniconda python distribution, use "-p" to select install location. For example:

```bash
sh ~/Downloads/Miniconda3-py311_24.1.2-0-Linux-x86_64.sh -bfsm -p ~/miniconda3
```

* Activate anc clone default environment into another named "appenv" 

```bash
eval "$(~/miniconda3/bin/conda shell.bash hook)"
conda create --name appenv --clone base
conda activate appenv
```

* Install dependency libraries

```bash
conda install pyqt
conda install numpy
conda install conda-pack
```

* Install pytorch. Please look up exact commands depending on OS and Cuda versions at <>

* Linux example
```bash
conda install pytorch pytorch-cuda=11.8 -c pytorch -c nvidia
```

* MacOS example:

```bash
conda install pytorch::pytorch -c pytorch
```

* Install rest of the dependencies
```bash
pip install -r requirements.txt
```

* Pack append environment into a portable tar file

```bash
conda pack --ignore-missing-files -n appenv
```

* Unpack environment to flameTimewarpML folder

```bash
mkdir  {flameTimewarpML folder}/packages/.miniconda/appenv/
tar xvf appenv.tar.gz -C {flameTimewarpML folder}/packages/.miniconda/appenv/
```

* Remove environment tarball

```bash
rm appenv.tar.gz
```
