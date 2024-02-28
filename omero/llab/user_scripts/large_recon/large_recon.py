#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) <year> Open Microscopy Environment.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Generates a downsampled image
"""
import os
import asyncio
import tempfile
from time import time

from omero import scripts, gateway
from omero.rtypes import rlong, rstring, robject, rint

import numpy as np
from skimage import io, transform, img_as_ubyte

import PIL.Image
PIL.Image.MAX_IMAGE_PIXELS = 933120000

from lavlab.omero_util import getImageAtResolution, OMERO_DICTIONARY

def idsToImageIds(conn, dType, rawIds):
    """
    Gathers image ids from given OMERO objects.

    Takes Project and Dataset ids. Takes Image ids too for compatibility.
    """
    if dType != "Image" :
        # project to dataset
        if dType == "Project" :
            projectIds = rawIds; rawIds = []
            for projectId in projectIds :
                for dataset in conn.getObjects('dataset', opts={'project' : projectId}) :
                    rawIds.append(dataset.getId())
        # dataset to image
        ids=[]
        for datasetId in rawIds :
            for image in conn.getObjects('image', opts={'dataset' : datasetId}) :
                ids.append(image.getId())
    # else rename image ids
    else : 
        ids = rawIds
    return ids

def main(conn,ids):
    start = time()
    for id in ids:
        img = conn.getObject("image", id)
        name = img.getName()
        sizeC = img.getSizeC()
        reconBin=None
        desiredRes = (int(img.getSizeY() / downsampleFactor),
                      int(img.getSizeX() / downsampleFactor),
                      sizeC)
        reconPath = tempfile.gettempdir() + os.sep + f"LR{downsampleFactor}_{name.replace('.ome.tiff',EXT)}"
        recon = img.getAnnotation(NS)
        
        if recon is None:  
            print(f"Downsampling: {name} from {(img.getSizeY(),img.getSizeX(), img.getSizeC())} to {desiredRes}")

            reconBin = getImageAtResolution(img, desiredRes)
            if saveFormat == 'JPEG':
                io.imsave(reconPath, reconBin,quality=100)
            else:
                io.imsave(reconPath, reconBin)
            
            print("Downsampling Complete! Uploading to OMERO...")
            recon = conn.createFileAnnfromLocalFile(reconPath, mimetype=MIME, ns=NS)
            img.linkAnnotation(recon)

            client.setOutput("File_Annotation", robject(recon._obj))

        else: 
            print("Large Recon already exists! Check in the attachments section. Delete the previous Large Recon to generate a new one.")
        
        if os.path.isfile(reconPath):
            os.remove(reconPath)
        
    print(f"Script took: {time()-start}")
        

if __name__ == "__main__":
    # allowed datatypes
    dataTypes = [
        rstring('Image'),
        rstring('Dataset'),
        rstring('Project')
    ]

    # allowed downsample factors
    dsFactors = [
        rint(10),
        rint(8)
    ]

    # from OMERO_DICTIONARY["SKIMAGE_FORMATS"]
    imgTypes = [
        rstring('JPEG'),
        rstring('TIFF'),
        rstring('PNG')
    ]
    client = scripts.client(
        'Large Recon', """Generates a downsampled image for processing""",
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=dataTypes, default=dataTypes[0]
        ),

        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of Ids to process.").ofType(rlong(0)
        ),
        scripts.Int(
            "Downsample_Factor", optional=False, grouping="2",
            description="What factor to downsample by?",
            values=dsFactors, default=dsFactors[0]
        ),
        scripts.String(
            "Save_Format", optional=False, grouping="3",
            description="What format to save recon as?",
            values=imgTypes, default=imgTypes[0]
        ),
        version="1",
        authors=["Michael Barrett"],
        institutions=["LaViolette Lab"],
        contact="mjbarrett@mcw.edu",
    )

    try:
        conn = gateway.BlitzGateway(client_obj=client)
        
        rawIds = client.getInput("IDs", unwrap=True)
        dataType = client.getInput("Data_Type", unwrap=True)
        saveFormat = client.getInput("Save_Format", unwrap=True)
        downsampleFactor = client.getInput("Downsample_Factor", unwrap=True)

        ids = idsToImageIds(conn, dataType, rawIds)

        # parse image save format
        EXT = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["EXT"]
        MIME = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["MIME"]

        NS = "LargeRecon."+str(downsampleFactor)
        
        # run processing
        main(conn, ids)
        # client.setOutput("Message", rstring("Success")) 

    except Exception as e:
        print(e)
        # client.setOutput("Message", rstring("Failed"))

    finally:
        conn.close()