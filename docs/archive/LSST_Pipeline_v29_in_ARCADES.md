# **Setup for ARCADES machine**

Terminal commands are in code blocks

Note \- The LSST pipeline is updated frequently.  Current version, as of this writing is v29. 

Please read the Other Stuff and Nonsense section for helpful tips and tricks as you work through this “cookbook”.

Steps 0 through 4 (except part of 1\) should already be done when working from the science pipeline container, unless new data is being fed into the system.

All needed scripts reside inside /arc/projects/NewHorizons/HSC\_2024/scripts, it is recommended to work from pwd HSC\_2024 for convenient access to both scripts and the butler repository

## **Step 0 \- Download all the data**

Most data (2020 \- 2024\) will already be there, but in case they’re not…  Use some magic to get the tar files from Subaru into your working directory. Once that is done, run the following: 

How to get data : 

* Open a desktop from science portal on canfar  
* Open web browser and go to [smoka.nao.ac.jp](http://smoka.nao.ac.jp)  
* Request an account   
* Search HSC catalogue and add a range for days of observation you want to pull data from, specify filter(s), and type (domeflat/bias/science) \[DON’T RESOLVE\]  
* Data compression : No collection, FPACK(.fz)  
* There will be 2 emails : the first is a confirmation that you have requested data and the second is for the data itself  
* Type in the command for downloading all the tar files (-wget) in whichever directory you want them in  
* At the end, do an md5sum check; this will cross reference the wget’s downloads with the .md5 file and see if everything has downloaded correctly 

| export RAW\_FILES \= '/arc/projects/NewHorizons/HSC\_2024/whatever/you/want'mkdir \$RAW\_FILEScd \$RAW\_FILEStar xf ../tar\_file.tarpython3 zadmin/unpack.py^C \#stop it after it makes inbound.txtcat zadmin/inbound.txt \| parallel |
| :---- |

## 

## **Step 1 \- Set up the .bash the environment**

Start by making all of the required directories. Still, you don’t have to create anything, just name these variables for convenience in your .bashrc file (a shell script natively built inside your \$HOME directory that is sourced whenever you open up a terminal). Butler, configs, and pipelines should be there already:

| export HSC\_2024=/arc/projects/NewHorizons/HSC\_2024 export BUTLER\_DIR=\${HSC\_2024}/PG2\_BUTLERexport PIPE\_DIR=\${HSC\_2024}/pipelinesexport CONFIG\_DIR=\${HSC\_2024}/configs |
| :---- |

Now set up your environment so that it looks for OUR instrument files with the New Horizons filter defined, not the LSST defaults. Be very careful with the order of your statements, as source\_injection overwrites portions of obs\_subaru if run after it:

| if \[ \-d /opt/lsst \]; then     export SHELL\=/bin/bash     export USER\=\$(whoami)     .  /opt/lsst/software/stack/loadLSST.bash     setup lsst\_distrib     setup \-r /arc/projects/NewHorizons/source\_injection \-t  \${USER}     setup \-r /arc/projects/NewHorizons/obs\_subaru \-t \${USER}     echo 'echo' fi |
| :---- |

Note that this must be done **EVERY TIME (put it in your bash for your own sake)** you start a new lsst terminal. Confirm this worked by running:

| pydoc lsst.obs.subaru |
| :---- |

The path should now start with /arc/projects/NewHorizons/obs\_subaru/ 

~~I also recommend including this statement, it preemptively sources many functions we will use later on~~

~~source /arc/projects/NewHorizons/HSC\_2024/scripts/sk\_utils.sh~~

We now use the \`canfar\` python module for job launching.

## **Step 2 \- Create the butler**

Create and set up the butler for HSC; the project now uses a PostgreSQL servery that is running on a host in CANFAR OpenStack (in the UVicKBOs project). 

|  butler create —seed-config \\ /arc/projects/NewHorizons/HSC\_2024/butler-seed.yaml –override I will schedule some time for us to connect. \$BUTLER\_DIR butler create \$BUTLER\_DIR butler register-instrument \$BUTLER\_DIR lsst.obs.subaru.HyperSuprimeCam butler write-curated-calibrations \$BUTLER\_DIR lsst.obs.subaru.HyperSuprimeCam |
| :---- |

## 

## **Step 3 \- Ingest the raw images**

Ingest the raw data. Modify the path to reflect the bias and flat data relevant to the night in question (this should already be downloaded in Step 0).

|  butler ingest-raws \$BUTLER\_DIR /arc/projects/NewHorizons/raw/data/ \-t link |
| :---- |

Confirm the ingestion worked:

| butler query-dimension-records \$BUTLER\_DIR exposure \--where "instrument='HSC' AND exposure.observation\_type='bias' and day\_obs=...." butler query-dimension-records \$BUTLER\_DIR exposure \--where "instrument='HSC' AND exposure.observation\_type='domeflat' and day\_obs=..." |
| :---- |

These commands should output tables of “familiar-looking calibration exposures”. If not, it’s time to debug.

If you need to remove some previous data from the butler you can remove datasets and collections using:

butler prune-datasets \$BUTLER\_DIR HSC/raw/all \--purge HSC/raw/all \--where "instrument='HSC' AND day\_obs=YYYYMMDD" \--find-all

Once the exposures are properly ingested, we can group them together into visits using the define-visits subcommand:

| butler define-visits \$BUTLER\_DIR lsst.obs.subaru.HyperSuprimeCam –-where “instrument=‘HSC’ AND day\_obs=\<insert day obs like 20250722\>” |
| :---- |

## 

## **Step 4 \- Generate a reference catalogue**

Next, we must ingest the reference catalogue. Start by registering the new refcat dataset type:  
Once more, these are done, only bother if introducing new data.

| butler register-dataset-type \$BUTLER\_DIR ps1\_pv3\_3pi\_20170110 SimpleCatalog htm7 butler register-dataset-type \$BUTLER\_DIR gaia\_dr3\_20230707 SimpleCatalog htm7 |
| :---- |

Now run the following Python script to create a .ecsv lookup table for the butler ingest-files command.

| """Generate an astropy-readable .ecsv lookup file for \`butler ingest-files\`, to ingest an existing gen2 refcat."""import osimport globimport astropy.tableps\_refcat\_dir \= "/path/to/refcats/ps1\_pv3\_3pi\_20170110"gaia\_refcat\_dir \= "/path/to/refcats/gaia\_dr3\_20230707"out\_dir \= "/path/to/my/output/directory"refcats \= \[ps\_refcat\_dir, gaia\_refcat\_dir\]for refcat\_dir in refcats:    out\_file \= f"{out\_dir}/{os.path.basename(refcat\_dir)}.ecsv"    table \= astropy.table.Table(names=("filename", "htm7"), dtype=("str",                                  "int"))    files \= glob.glob(f"{refcat\_dir}/\[0-9\]\*.fits")    for i, file in enumerate(files):        \# running status, overwriting each print statement as it proceeds        print(f"{i}/{len(files)} ({100\*i/len(files):0.1f}%)", end="\\r")        \# extract file index; add row to table        file\_index \= int(os.path.basename(os.path.splitext(file)\[0\]))        table.add\_row((file, file\_index))    table.write(out\_file)    print(f"Output written to: {out\_file}") |
| :---- |

Once this has finished, we can finish the reference catalogue ingestion.

| butler ingest-files \-t direct \$BUTLER\_DIR ps1\_pv3\_3pi\_20170110 refcats/gen2 \<PS1 FILENAME\> butler ingest-files \-t direct \$BUTLER\_DIR gaia\_dr3\_20230707 refcats/gen2 \<GAIA FILENAME\> butler collection-chain \$BUTLER\_DIR \--mode extend refcats refcats/gen2 |
| :---- |

Confirm the ingestion worked by running the following to see whether your htm shards appear:

| butler query-datasets \--collections refcats \$BUTLER\_DIR |
| :---- |

## 

## **Step 5 \- Create the calibration images**

Create flats and biases. First, create the bias frames for each chip. The command below is an example of the process in a format suitable for running on the command line. This is heavy, can lead to many undocumented errors, and is hard to keep track of. For this and every following step, we have moved on to the Qgraph system (see the Qgraphs section). 

| pipetask run \--register-dataset-types \\ \-b \$BUTLER\_DIR \\ \-i HSC/raw/all,HSC/calib \\ \-o u/NH/bias-construct \\ \-p \$CP\_PIPE\_DIR/pipelines/HSC/cpBias.yaml \\ \-d "instrument='HSC' AND exposure.observation\_type='bias' AND NOT detector=9" \\ \-c cpBiasIsr:doVignette=False \\ \-j 32 |
| :---- |

This step uses the script create\_dated\_full\_bias\_qgraphs.sh, it will create a bias calibration for each detector between the specified edges for the range of dates requested. Bias and flat calibrations are loosely valid for about 30 days.

| scripts/create\_dated\_full\_bias\_qgraphs.sh start\_detector end\_detector start\_date end\_date |
| :---- |

Dividing the biases/flats per month according to the following catalogue (personal choice):  
may2020 → 20200519, 20200526, 20200528, 20200529, 20200530, 20200531, 20200601, 20200619, 20200620, 20200621, 20200622, 20200624, 20200625\. 20 bias frames, 20 flat frames (so many)  
jun2021 → 20210609, 20210617, 20210705. 10 bias frames, 10 flat frames  
sep2021 → 20210905, 20210906. 20 bias frames, 0\!\! flat frames  
jun2022 → 20220602, 20220603, 20220629, 20220630, 20220703. 20 bias frames, 20 flat frames  
oct2022 → 20221020, 20221021, 20221023. 15 bias frames, 11 flat frames  
sep2023 → 20230908, 20230909, 20230910. 10 bias frames, 20 flat frames  
jun2024 → 20240611, 20240612, 20240705, 20240708, 20240709, 20240710. 6 bias frames, 20 flat frames (sus)  
jul2024 → 20240731, 20240801, 20240802. 15 bias frames, 11 flat frames

 Now certify the bias frames into a calib collection:

| butler certify-calibrations \$BUTLER\_DIR u/NH/bias-construct HSC/calib/run1 bias |
| :---- |

You can optionally specify the beginning and end date of the validity range for the certified calibrations using \--begin-date and \--end-date. Datetimes must be in ISO-8601 format. Meaning YYYY-MM-DD with the hyphens

Preferable even is using the calibrate.sh script as follows:

| scripts/calibrate.sh bias collection/path start\_date end\_date |
| :---- |

This will automatically certify your calibrations for the whole specified range with a 2 day leeway to over-account for potential timezone issues.

Now we must create the flat frames for each chip:

| pipetask run \--register-dataset-types \\ \-b \$BUTLER\_DIR \\ \-i HSC/raw/all,HSC/calib \\ \-o u/NH/flat-construct \\ \-p \$CP\_PIPE\_DIR/pipelines/HSC/cpFlat.yaml \\ \-d "instrument='HSC' AND exposure.observation\_type='domeflat' AND NOT detector=9" \\ \-c cpFlatIsr:doBias=False \\ \-c cpFlatIsr:doDark=False \\ \-j 32 |
| :---- |

This time, we are using create\_full\_flat\_qgraphs.sh script. It is extremely similar to the script used for creating biases and takes the exact same commands in the same order.

And certify the flat frames into a calib collection:

| butler certify-calibrations \$BUTLER\_DIR u/NH/flat-construct HSC/calib/run1 flat |
| :---- |

Similarly to biases, you can optionally specify the beginning and end date of the validity range for the certified calibrations using \--begin-date and \--end-date. Datetimes must be in ISO-8601 format.

And again, you can use calibrate.sh in a very similar manner to before, only this time swapping the argument “bias” for “flat” and directing it to the correct collection path.

## 

## **Step 6 \- Process the science frames**

Before running processCCD, run this to generate your injection catalog. There is a script called create\_daily\_fakes.sh that can be helpful. As functional as the syntax is, that script does not have a good way of directly sourcing the required parameters and as of now requires manual input. My strategy was to note down what was needed in an excel spreadsheet and print out the columns as lists using jupyter, to then paste them in the script. Feel free to optimize this step.

| generate\_sso\_injection\_catalog \-a {ra} \-d {dec} \-r 2 \-b \$BUTLER\_DIR \-s 4000 –day-obs {date} \-i {band} \-o fakes/{date} \--seed {whatever 8-digit number}  |
| :---- |

To obtain the values you need for this step, run:

| for date in \${dates\[@\]}; do butler query-dimension-records PG2\_BUTLER/ exposure \--where "instrument='HSC' AND day\_obs=\${date} AND detector=50 AND observation\_reason='science'" \--limit 4; done |
| :---- |

Besides everything you need, also note down the target name for each of these dates, and then rerun individual queries while adding to the –where clause “AND NOT target\_name=’target’”. Hopefully it returns empty or with just fodder like “TEST”. However, if another target is present and has a different sky position, another catalog might need to be made. Consult with JJ if this is the case as it may be ignorable.

Execute processCCD on the science data:

| pipetask run \--register-dataset-types \\\-b \$BUTLER\_DIR \\\-i HSC/raw/all,refcats,HSC/calib,HSC/calib/run1,fakes/{date} \\\-o u/NH/processCCD \\\-p \$PIPE\_DIR/DRP-Prod+injection\_upd.yaml\#processCcd \\\-d "instrument='HSC' AND visit.observation\_reason='science' AND detector.purpose='SCIENCE' AND NOT detector=9" \\\-c isr:doDark=False \\\-j 32 |
| :---- |

Again be efficient and use the create\_processCCD.sh script, works quite similarly to the other ones. Note the new parameter obs\_month is something automatically defined on the previous steps of the pipeline given the range of dates you inputted for calibrations. It has the format monyear (for instance, jun2021) based on the earliest day within your range. If the dataset is new and not present in the catalog from a few pages above, you will have to add it manually within the script, but following the syntax should be quite simple.

| scripts/create\_processCCD.sh start\_det end\_det obs\_month |
| :---- |

## **Step 7 \- Produce the implanted imagery**

This whole step was done before processCCD with the new pipeline, keeping it here for no good reason other than preserving history, move on.

Now we are ready to produce the implanted imagery. From here on, the processing must be run in an **lsst\_v27** image. To do planting, we will use the lsst.source.injection package. First, we need to generate an injection catalogue:

| generate\_injection\_catalog \\\-b \$BUTLER\_DIR\-i gri\-o u/NH/injection\_catalogue |
| :---- |

Now we can actually produce some images with planted sources:

| pipetask run \--register-dataset-types \\\-b BUTLER\_DIR \\\-i u/NH/processCCD,u/NH/injection\_catalogue \\\-o u/NH/planted \\\-p \$PIPE\_DIR/NHPipeline+injection.yaml\#inject\_visit |
| :---- |

## 

**Step 8 \- Final Processing**

The next bit of processing requires a SkyMap, so we will run the following to create one: Only if for some reason you want to run it one detector at a time.

| scripts/make\_discrete\_skymap.sh \$BUTLER\_DIR process/CCD/collection day\_obs detector |
| :---- |

The new approach is to make one massive skymap per year, encompassing all observation days and all detectors at once. Note that this will cause many quanta in the warping stage to be empty and get skipped, however that is to be expected as that step is ran by detector and not all patches of the skymap will align with a detector’s data. The way to call this function is to give it the year you are making the skymap for and give it one exposure from each night to ensure it covers the entire observed area of that year (field of view barely moves during one given night, so more than 1 exposure per night is unnecessary and will take longer with no benefits)

| scripts/make\_big\_skymap.sh YYYY date1\_exp date2\_exp . . . date\_last\_exp |
| :---- |

~~Next, we will run completeProcessing on the data, which will create a per-visit source table which the butler needs for further calibration.~~ I am for preserving history but we have completely changed this step, don’t get confused. At this point we need visit summaries (even though we will not use them) so that the processing can continue. In this case, the dates are divided just as they were in processCCD, but with all detectors at once. We will run:

| scripts/create\_visits.sh obs\_month |
| :---- |

Now for the big processing with upwards of 5000 quanta we are using DRP-Prod+injection\_upd\#newHorizons, which includes 8 subtasks that will end up with difference images in the format of injected\_goodSeeingDiffs\_differenceTempExp. The point of the subset is to join steps 8, 10 and 11 of this manual, so disregard the coding blocks that come after the very next one and run.

| scripts/create\_image\_diffs.sh detector\_low detector\_high obs\_month |
| :---- |

Works with the same parameters as create\_processCCD.sh, only on a different subset of the pipeline.

| pipetask run \--register-dataset-types \\\-b \$BUTLER\_DIR \\\-i u/NH/processCCD,skymaps \\\-o u/NH/completeProcessing \\\-p \$PIPE\_DIR/NHPipeline.yaml\#completeProcessing \\\-j 32 |
| :---- |

## **Step 9 \- Global Calibration**

To improve our photometric and astrometric calibrations, and to calibrate across all of the data, we will use jointcal: Never worked, maybe this time.

| pipetask run \--register-dataset-types \\\-b \$BUTLER\_DIR \\\-i u/NH/completeProcessing \\\-o u/NH/jointcal \\\-p \$PIPE\_DIR/NHPipeline.yaml\#jointcal \\\-c jointcal:doPhotometry=True |
| :---- |

Finally, we will apply the calibrations:

| pipetask run \--register-dataset-types \\\-b \$BUTLER\_DIR \\\-i u/NH/completeProcessing,u/NH/fgcm,u/NH/gbdes \\\-o u/NH/calibrated \\\-p \$PIPE\_DIR/NHPipeline.yaml\#applyCalibrations\-j 32 |
| :---- |

## **Step 10 \- Create a template for difference imaging**

Now, create the template using the makeTemplate task: Skipped

| pipetask run \--register-dataset-types \\\-b \$BUTLER\_DIR \\\-i u/NH/calibrated \\\-o u/NH/warps \\\-p \$PIPE\_DIR/NHPipeline.yaml\#makeTemplate \-c makeWarp:doApplySkyCorr=False \\ \-j 32 |
| :---- |

## **Step 11 \- Produce the difference images**

Finally, perform the difference imagery using the imageDifference task: Skipped.

| pipetask run \--register-dataset-types \\\-b \$BUTLER\_DIR \\\-i u/NH/coadds \\\-o u/NH/difference \\\-p \$PIPE\_DIR/NHPipeline.yaml\#imageDifference \\ \-j 32 |
| :---- |

Congratulations\! You’ve successfully processed New Horizons data and learned some LSST pipeline. Now send these diffs to the rest of the team, maybe Wes, and let them run shift and stack and see if it works. We never got this far, but surely there’s more science after this.

**Step 12 \- Quality Assurance Pipelines**

There are some analysis tools that can be used to do some quality assurance on the end products of processing.  
The location of the all quality assurance pipelines is at (confirmed location) : 

| /opt/lsst/software/stack/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/analysis\_tools/g57a72a660c+84b06d847d/pipelines |
| :---- |

The most ‘relevant’ pipelines are the following : 

* **visitQualityCore.yaml** \- analyzes the quality of visit level data (used to be called ***calexpMetrics.yaml*** which analyze calibrated exposures) \[procCCD products can be input here\]  
* **visitQualityExtended.yaml** \- used to look deeper into any problem that arises in the visit level data/look deeper into data quality  
* **cpCore.yaml** \- used to assess quality of calibration products (post Bias and Flat calibrations)  
* **wholeSkyCore.yaml** \- used to assess quality of whole sky (i think this refers to skymap)


## **Processing multiple visits at once (Qgraphs)**

The general idea of the qgraph system is running multiple processes in parallel with headless processing. This bunch of words means that it will be faster and not take up terminal space on your own simulated desktop, which is quite handy. A problem to be aware of is that headless processes are lower on the priority list of the cluster, so if memory is needed for an active job somewhere the first things to be shut down are the headless. All qgraphs are stored within one of the subdirectories inside \$BUTLER\_DIR/qgraphs, and the steps below will assume that to be the pwd.

The barebones of how it works is:

* A script creates a qgraph using a “pipetask qgraph” command with however many specifications, that qgraph contains all the information on how to run the desired task.  
* This script goes to the hold/ directory, from which you can move it to the queue/ directory if you intend to run it  
* Once the queue/ is populated with anything, you can run a qrunner with the script launch\_qrunners.sh, which takes a starting and ending indexes, generating however many are in between those. Common usage would be scripts/launch\_qrunners.sh 1 20 to launch 20 qrunners, for instance. Qrunners will each take one qgraph from the queue/ and work through it. Once they are done, they will pick up the next one and keep going until queue/ is empty again. Each qrunner currently takes 1 CPU core and 4GB of RAM, this proved to be sufficient for everything we have done up to now, but it can be edited on that same script if needed  
* Ongoing processes will be in the processing/ directory, while finished ones will go to the processed/ directory. A log of the execution is written to the logs/ directory parallel to the processing and can be followed in real time with the “tail \-f” command.  
* When a process is done, it is good practice to inspect its log and check if anything failed before proceeding, as it is much easier to discard a bad run before it is put inside the butler. If no errors exist, you can move everything from processed/ into examined/  
* Once in examined/ the script merge.sh (which takes no positional arguments) will take every qgraph within it and transfer that data to the butler so that it can be worked with in the subsequent steps of the processing. This is quite a lengthy step. If anything went wrong with the merging, the qgraph will go to the failed/ directory. If not, it will be moved to the merged/ directory and you will never find (or need to find) it again.

Notes

- Qrunners often crash for no good reason, this will lead to qgraphs getting stuck inside the processing/ directory with no runners running in the background. When this happens, simply remake those graphs and delete the ones that got stuck, rinse and repeat.   
- If the runner happens to run out of memory, it will not crash but move the graph to processed/ without actually finishing it. This is part of why checking the logs is an important part of the process.  
- The amount of memory a qrunner has is specified by YOU on the script. I’ve found that 2GB is enough for calibrations, 4GB for processCCD and 16GB for the newHorizons subset. Keep the available RAM from Canfar in mind when launching runners.  
- Most of these processes can be run in parallel, I often have separate graphs being created, processed and merged in 3 different terminals at the same time.  
- The –output-run and –extend-run subcommands of the pipeline seem to have issues with the qgraphs, fixing it would be optimal for organizational purposes.

## **Other Stuff and Nonsense**

1. Note: Readout of HSC’s detector 9 has been suspended since 2018, and so will fail when creating flat frames, bias frames and running processCcd. Therefore we specify the data query \-d "NOT detector=9".  
     
2. If you need to restart a task because some quanta failed, or the task didn’t manage to complete for any reason, rerun the command using and add \--skip-existing-in \<OUTPUT COLLECTION NAME\> to the end of the command.  
     
   1. If you had to rerun the bias or flat construction task, add \--search-all-inputs to the certify-calibrations command. This will ensure that the calibrations for *all* detectors are certified.  
   2. You also cannot recertify calibrations over the same date range on the same collection if specified, so in the unfortunate case that something went wrong and it got certified, your best bet is to make a new calibration collection altogether by editing the calibrate.sh script output.

3. Specifying \-j \<NUM CORES\> to execute processes in parallel can only be used if multiple visits are being processed. Trying to process multiple detectors at once for a single visit will result in a database lock error.  
   1. On the qgraph side of things, launch as many qrunners as you think your process deserves to be run in parallel, overshoot it to account for crashes.

4. To filter by day use "day\_obs=\<YYYYMMDD\>". 

5. It is possible to transfer datasets from one butler to another. This is especially useful if you have calibrations that you want to use for multiple nights, but the different nights are in different butlers. Use the following to transfer datasets:  
   

| butler transfer-datasets \$BUTLER\_DIR \$NEW\_BUTLER\_DIR \--register-dataset-types \-t copy |
| :---- |

   

   You can optionally specify the dataset type or collections that you want transferred with \-d and \--collections respectively. See the lsst [butler transfer-datasets](https://pipelines.lsst.io/modules/lsst.daf.butler/scripts/butler.html#butler-transfer-datasets) documentation for more options.

6. If you are interested in visualising the pipeline, run the following command:

| pipetask build \-p \$PIPE\_DIR/NHPipeline.yaml \--show pipeline |
| :---- |

	  
Alternatively, if you want to visualise the quantum graph to understand how the tasks and datasets are interconnected, run:

| pipetask build \-p \$PIPE\_DIR/NHPipeline.yaml \--pipeline-dot /tmp/pipeline.dot dot /tmp/pipeline.dot \-Tpdf \> NH\_pipeline.pdf |
| :---- |

7. I often find random visit/detector combinations will fail (for no good reason at all). Therefore, you will need to run the task (it’s processCcd who are we kidding?) that results in failure more than once. Generally, for processCcd, I run the processCcd\_qbb.sh script in scripts to get most of the visits/detectors out of the way. Once those are finished merging, rebuild a quantum graph for ALL remaining quanta. Then run a quantum-backed butler for this graph with \-j 32, and merge when finished. Repeat until the only quanta still failing at least have a decent reason to be failing. Then you’re on your own to figure out what to do with the remaining quanta\! Good luck\!  
   1. I find the failing visits are always systemic and have something to do with bad quality of the data, this is usually only about 1 or 2 per night so don’t bother too much with it.

8. You can search a previous command with ctrl+R instead of hitting up arrow forever, handy. Hitting ctrl+R again will go to the next command that matches your string. Ctrl+G will take you out of reverse search mode.  
      
9. Many things will get you stuck in a weird sub-tool of the terminal. Ctrl+C or a combination of Ctrl+X and then Ctrl+C should get you out of most of them (and also cancel a lot of commands or scripts), but in an urgent and desperate scenario don’t be scared to hit Ctrl+Z and deal with it later (won’t ever be a big issue)  
      
10. The commands “more” and “tail” are generally more useful for debugging readability than simply “cat”. “tail \-f” is especially useful for inspecting ongoing qrunners, as it follows the log file as it is being written.  
       
11. The disk might run out of space, a clear indicator of this (if not from an obvious error message) is the inability to save script changes which pop out a red warning if tried, ask JJ for more.  
       
12. Creating a script will always require you to give it execution permission before running it. Do that with “chmod \+x scripts/script\_name.sh” on your command line.  
       
13. Anytime you want to display anything on ds9, the script display\_frame.sh is your friend. Quite easily editable, different frame types require different parameters, which are up to you to find out if I haven’t done it already.

14. Be very careful of duplicates on the database. Tested and true: skymaps will not be created if there are two datasets with the same identification (caused by merging halfway-done qgraphs). For this, I like to use the following command:   
    1. grep \-L "and 0 remain" PG2\_BUTLER/qgraphs/logs/processCCD-2025\*  
    2. The string is an identifier of a complete processing, while the \-L (case sensitive) will list all logs that do not contain it.

## **Useful links**

[butler — LSST Science Pipelines](https://pipelines.lsst.io/modules/lsst.daf.butler/scripts/butler.html#butler-query-dataset-types)

[pipetask — LSST Science Pipelines](https://pipelines.lsst.io/modules/lsst.ctrl.mpexec/pipetask.html#pipetask-run-qbb)

[Getting started with the LSST Science Pipelines — LSST Science Pipelines](https://pipelines.lsst.io/getting-started/index.html)

[https\://kinsta.com/blog/linux-commands/](https://kinsta.com/blog/linux-commands/)

[https\://docs.google.com/spreadsheets/d/1O0ohRrrAQyOkiQkvuHLgEZjvvXA43WA6yoJio7IFJ3Y/edit?usp=sharing](https://docs.google.com/spreadsheets/d/1O0ohRrrAQyOkiQkvuHLgEZjvvXA43WA6yoJio7IFJ3Y/edit?usp=sharing)  
