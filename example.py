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
DOC STRINGS (the 6 quote string under something) SHOW UP WHEN YOU HOVER
"""
from time import time
from omero_model_ImageI import ImageI
from omero import scripts, gateway
from omero.rtypes import rlong, rstring, robject, rint
import PIL.Image
PIL.Image.MAX_IMAGE_PIXELS = 933120000

from lavlab.omero_util import OMERO_DICTIONARY, idsToImageIds, getTiles

def main(conn: gateway._BlitzGateway, ids: list[int]):
    start = time()

    # for each image
    for id in ids:
        # get object from id
        img_obj = conn.getObject('Image', id)
        assert type(img_obj) is ImageI # gives autofill results
        # do processing in here
        # (OME) img_obj.getPrimaryPixels().getTiles()
        # (LavLab) lavlab.omero_util.getClosestResolution()
        # remember to clean up your loop runs!
    
    print(f"Script took: {time()-start}") # optional
        
# if name is main, initialize
if __name__ == "__main__":
    # allowed object types
    # these 3 are typical choices as they can be broken down to one list of image ids
    object_types = [
        rstring('Image'),
        rstring('Dataset'),
        rstring('Project')
    ]


    # lavlab-python-utils uses scikit-image for file writing
    supported_save_formats = OMERO_DICTIONARY["SKIMAGE_FORMATS"].keys()


    client = scripts.client(
        'SCRIPT NAME', [""" SINGLE LINE""", """or multi lined description"""],
        # define variables for ui
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=object_types, default=object_types[0]
        ),
        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of Ids to process.").ofType(rlong(0)
        ),
        scripts.String(
            "Save_Format", optional=False, grouping="2",
            description="What format to save result as?",
            values=supported_save_formats, default=supported_save_formats[0]
        ),
        scripts.Float(
            "YOUR_VARIABLE", optional=False, grouping="3",
            description="The description. This variable is a 32bit decimal number",
           default=0.0
        ),
        version="1",
        authors=["YOUR NAME HERE"],
        institutions=["LaViolette Lab"],
        contact="email@mcw.edu",
    )

    try:
        conn = gateway.BlitzGateway(client_obj=client)
        
        # ids + datatype variables are the OME supported method of selecting data to run on
        # these two inputs allow highlighting data in omero web to run a script on
        rawIds = client.getInput("IDs", unwrap=True)
        dataType = client.getInput("Data_Type", unwrap=True)

        # gather other ui variables
        saveFormat = client.getInput("Save_Format", unwrap=True)
        # getInput("name of variable", always do unwrap=True)
        variable = client.getInput("YOUR_VARIABLE", unwrap=True)

        # lavlab-python-util function to convert datatype+ids (image, dataset, project) into a list of image ids
        ids = idsToImageIds(conn, dataType, rawIds)

        # parse extension for saving, and mime type for uploading
        # lavlab-python-utils/omero_util.py has a dictionary for use in omero
        EXT = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["EXT"][0]
        MIME = OMERO_DICTIONARY["SKIMAGE_FORMATS"][saveFormat]["MIME"]
        
        # run script
        main(conn, ids)
        # if it didn't fail it succeeded
        client.setOutput("Message", rstring("Success")) 

    except Exception as e:
        # print exception and mark as failed
        print(e)
        client.setOutput("Message", rstring("Failed"))

    finally:
        # FINAL CLEANUP HERE
        conn.close()