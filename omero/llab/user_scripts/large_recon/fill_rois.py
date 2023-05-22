import os
import logging

from tempfile import TemporaryDirectory,gettempdir
from omero import scripts, gateway

from omero.rtypes import rlong, rstring, robject, rint
from skimage import io

import large_recon

from lavlab.python_util import save_image_binary
from lavlab.omero_util import idsToImageIds,getShapesAsMasks, applyMask, downloadFileAnnotation, uploadFileAsAnnotation, OMERO_DICTIONARY


def main(conn, ids):
    for id in ids:
        img = conn.getObject("image", id)
        with TemporaryDirectory() as workdir:
            # get large recon for processing
            recon = img.getAnnotation(RECON_NS)
            if recon is None:
                logging.warning("No large recon for img: {id} Generating...")
                recon=large_recon.main(conn,[id])
            reconBin = io.imread(downloadFileAnnotation(recon, workdir))

            print("Gathering shapes...")
            for mask in getShapesAsMasks(img, downsampleFactor, False, polygonDownsample):
                applyMask(reconBin, mask)
            roiFilename = "FilledROIs_" + os.path.splitext(recon.getFile().getName())[0] + ROI_EXT
            roiPath = save_image_binary(workdir + os.sep +  roiFilename, reconBin)
            
            roiFilled=uploadFileAsAnnotation(img, roiPath, ROI_NS, ROI_MIME, conn)

            client.setOutput("File_Annotation",robject(roiFilled._obj))

            
if __name__ == "__main__":
    dataTypes = [
        rstring('Image'),
        rstring('Dataset'),
        rstring('Project')
    ]
    dsFactors = [
        rint(10),
        rint(8)
    ]
    supported_save_formats = OMERO_DICTIONARY["SKIMAGE_FORMATS"].keys()
    
    client = scripts.client(
        'Fill ROIs', """Creates a large recon with filled all available polygonal ROIs""",
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=dataTypes, default=dataTypes[0]
        ),
        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of Ids to process."
        ).ofType(rlong(0)),
        scripts.String(
            "Save_Format", optional=False, grouping="2",
            description="What format to save result as?",
            values=supported_save_formats, default=supported_save_formats[0]
        ),
        scripts.Int(
            "Downsample_Factor", optional=False, grouping="3",
            description="What factor to downsample by?",
            values=dsFactors, default=dsFactors[0]
        ),
        scripts.Int(
            "Polygon_Downsample", optional=False, grouping="3.1",
            description="Downsamples polygon outline for cheaper computing",
            default=4
        ),
        version="1",
        authors=["Michael Barrett"],
        institutions=["LaViolette Lab"],
        contact="mjbarrett@mcw.edu",
    )

    try:
        conn = gateway.BlitzGateway(client_obj=client)
        iScript = conn.getScriptService()
        roiService = conn.getRoiService()

        rawIds = client.getInput("IDs", unwrap=True)
        dataType = client.getInput("Data_Type", unwrap=True)
        saveFormat = client.getInput("Save_Format", unwrap=True)
        downsampleFactor = client.getInput("Downsample_Factor", unwrap=True)
        polygonDownsample = client.getInput("Polygon_Downsample", unwrap=True)

        ids = idsToImageIds(conn, dataType, rawIds)

        # parse image save format and namespace
        ROI_EXT = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["EXT"][0]
        ROI_MIME = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["MIME"]

        RECON_NS="LargeRecon."+str(downsampleFactor)
        ROI_NS=RECON_NS+".ROI"
        
        # run processing
        main(conn, ids)
        client.setOutput("Message", rstring("Success")) 

    except Exception as e:
        print(e)
        client.setOutput("Message", rstring("Failed"))

    finally:
        client.closeSession()