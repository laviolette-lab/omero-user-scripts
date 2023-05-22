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
import tempfile
from time import time

from omero import scripts, gateway
from omero.rtypes import rlong, rstring, robject, rint

from lavlab.python_util import save_image_binary
from lavlab.omero_util import OMERO_DICTIONARY, getImageAtResolution, idsToImageIds, getDownsampledYXDimensions

def main(conn,ids):

    NS = "LargeRecon."+str(downsampleFactor)
    recons = []
    for id in ids:
        img = conn.getObject("image", id)

        name = img.getName()
        sizeX = img.getSizeX()
        sizeY = img.getSizeY()

        yx_dim=getDownsampledYXDimensions(img, downsampleFactor)
        reconPath = tempfile.gettempdir() + os.sep + f"LR{downsampleFactor}_{name.replace('.ome.tiff',EXT)}"
        recon = img.getAnnotation(NS)
        
        if recon is None:  
            print(f"Downsampling: {name} from {(sizeY,sizeX)} to {yx_dim}")
            reconBin = getImageAtResolution(img, yx_dim)
            
            if saveFormat == 'JPEG': jpeg=True 
            else: jpeg=False

            save_image_binary(reconPath,reconBin, jpeg)
            
            print("Downsampling Complete! Uploading to OMERO...")
            recon = conn.createFileAnnfromLocalFile(reconPath, mimetype=MIME, ns=NS)
            img.linkAnnotation(recon)

            client.setOutput("File_Annotation", robject(recon._obj))

        else: 
            print("Large Recon already exists! Check in the attachments section. Delete the previous Large Recon to generate a new one.")
        
        # do this outside of if recon in case of a previous attempt residing there
        if os.path.isfile(reconPath):
            os.remove(reconPath)
        
        recons.append(recon)
    return recons
        
        

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

    supported_save_formats = OMERO_DICTIONARY["SKIMAGE_FORMATS"].keys()

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
            values=supported_save_formats, default=supported_save_formats[0]
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
        EXT = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["EXT"][0]
        MIME = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["MIME"]

        
        # run processing
        start = time()
        main(conn, ids)
        print(f"Script took: {time()-start}")
        client.setOutput("Message", rstring("Success")) 

    except Exception as e:
        print(e)
        client.setOutput("Message", rstring("Failed"))

    finally:
        conn.close()