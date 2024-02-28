import os
from tempfile import gettempdir

import omero
from omero import scripts, gateway
from omero.rtypes import rlong, rstring, robject, rint, wrap

from skimage import draw, io

import PIL.Image
PIL.Image.MAX_IMAGE_PIXELS = 933120000

def cleanup(workdir):
    for file in os.listdir(workdir):
        os.remove(workdir+os.sep+file)
    os.rmdir(workdir)

def getShapesAsPoints(roiService, img, downsampleFactor, polygonDownsample):
    shapes = []

    result = roiService.findByImage(img.getId(), None)
    res = [img.getSizeY() / downsampleFactor,
            img.getSizeX() / downsampleFactor]

    for roi in result.rois:
        points= None
        for shape in roi.copyShapes():
            if type(shape) == omero.model.RectangleI:
                x = int(shape.getX().getValue() / downsampleFactor)
                y = int(shape.getY().getValue() / downsampleFactor)
                width = int(shape.getWidth().getValue() / downsampleFactor)
                height = int(shape.getHeight().getValue() / downsampleFactor)
                points=draw.polygon([y+height, y+height, y, y],
                                    [x, x+width, x+width, x],
                                    shape=res)
                

            if type(shape) == omero.model.PolygonI:
                y = []
                x = []

                pointStrArr = shape.getPoints()._val.split(" ")
                for i in range(0, len(pointStrArr), polygonDownsample):
                    coordList=pointStrArr[i].split(",")
                    y.append(int(float(coordList[1]) / downsampleFactor))
                    x.append(int(float(coordList[0]) / downsampleFactor))

                points = draw.polygon(y, x, shape=res)

            if type(shape) == omero.model.EllipseI:
                points = draw.ellipse(int(shape._y._val / downsampleFactor),int(shape._x._val / downsampleFactor),
                                                int(shape._radiusY._val / downsampleFactor),int(shape._radiusX._val / downsampleFactor),
                                                shape=res)

            if points is not None:
                shapes.append((shape.getId()._val, shape.getStrokeColor()._val, points))

    if not shapes : 
        return None

    # make sure is in correct order
    return sorted(shapes)

def main(conn, ids):
    for id in ids:
        try:
            img = conn.getObject("image", id)
            workdir=gettempdir()+os.sep+"fill-rois-"+str(id)
            os.mkdir(workdir)
            
            # get large recon for processing
            recon = img.getAnnotation(RECON_NS)
            if recon is None:

                args={
                    'Data_Type': wrap('Image'),
                    'IDs': wrap([rlong(id)])
                }
                proc = iScript.runScript(SCRIPT_ID, args, None, conn.SERVICE_OPTS)
                cb = scripts.ProcessCallbackI(conn.c, proc)
                
                try:
                    print(f"No LargeRecon{downsampleFactor}! Generating a new one...")
                    while proc.poll() is None:
                        cb.block(1000)
                    print("Recon received: %s" % cb.block(0))
                    rv = proc.getResults(0)
                    if rv.get('stderr'):
                        print("Error. See file: ", rv.get('stderr').getValue().id.val)
                        
                    recon=conn.getObject("annotation", rv.get('File_Annotation').getValue().getId().getValue())
                finally:
                    cb.close()

            reconPath=workdir+os.sep+recon.getFile().getName()
            print(f"Downloading {reconPath}...")
            with open(reconPath, 'wb') as f:
                for chunk in recon.getFileInChunks():
                    f.write(chunk)
            print("File downloaded! Gathering shapes...")

            shapes = getShapesAsPoints(roiService, img,
                    downsampleFactor, polygonDownsample)
                    
            if shapes is None:
                print("No Shapes Found!")
                cleanup(workdir)
                break

            reconBin = io.imread(reconPath)

            print("Filling in rois")
            for shape in shapes:
                # create bitwize masks for color channels  
                redMask = 0xFF000000  
                greenMask = 0xFF0000  
                blueMask = 0xFF00  
                # alphaMask = 0xFF  

                # bitwize mask the integer into 8-bits each (get outline color)
                red = (shape[1] & redMask) >> 24  
                green = (shape[1] & greenMask) >> 16  
                blue = (shape[1] & blueMask) >> 8  
                # alpha = (shape[1] & alphaMask)  

                # fill shape with outline rgb vals
                reconBin[shape[2]] = [red,green,blue]

            roiPath = workdir + os.sep + "FilledROIs_" + recon.getFile().getName()
            io.imsave(roiPath, reconBin, quality=100)

            roiFilled = img.getAnnotation(ROI_NS)

            if roiFilled is not None:
                conn.deleteObjects('Annotation', [roiFilled.id], wait=True)
            
            roiFilled = conn.createFileAnnfromLocalFile(roiPath, mimetype=recon.getFile().getMimetype(), ns=ROI_NS)
            img.linkAnnotation(roiFilled)
            client.setOutput("File_Annotation",robject(roiFilled._obj))
        finally:
            cleanup(workdir)

            
if __name__ == "__main__":
    dataTypes = [
        rstring('Image'),
        rstring('Dataset'),
        rstring('Project')
    ]
    dsFactors = [
        rint(10)
    ]
    
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
        scripts.Int(
            "Downsample_Factor", optional=False, grouping="1.2",
            description="What factor to downsample by?",
            values=dsFactors, default=dsFactors[0]
        ),
        scripts.Int(
            "Polygon_Downsample", optional=False, grouping="2",
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

        # gather ids of individual images for processing
        if dataType.lower() != "image" :
            # project to dataset
            if dataType == "Project" :
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

        # constants
        SCRIPT_DIR="/llab/pipeline"
        RECON_NS="LargeRecon."+str(downsampleFactor)
        ROI_NS=RECON_NS+".ROI"
        # SCRIPT_ID=iScript.getScriptID(SCRIPT_DIR+"/Large_Recon.py")
        # large_recon is included in this package
        SCRIPT_ID=iScript.getScriptID("/large_recon.py")
        
        # run processing
        main(conn, ids)
        client.setOutput("Message", rstring("Success")) 

    except Exception as e:
        print(e)
        client.setOutput("Message", rstring("Failed"))

    finally:
        client.closeSession()