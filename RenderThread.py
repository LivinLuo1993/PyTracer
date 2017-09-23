import multiprocessing,numpy
from datetime import datetime
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from RenderProcess import RenderProcess

class RenderThread(QThread):
	#This is a separate thread from UI, this thread will spawn tasks to multi processing
	#This thread itself will be rendering as well
	updateImgSignal =pyqtSignal(QImage)

	def __init__(self,width,height,scene,cam):
		QThread.__init__(self)
		self.width = width
		self.height = height
		self.scene = scene
		self.cam = cam

	def getBucket(self,processCnt):
		#input the process count, return the starting point of each bucket
		startLine = []
		bucketHeight = int(self.height / processCnt)
		for i in range(0,processCnt):
			startLine.append(bucketHeight * i)

		return startLine, bucketHeight

	def getOrderKey(self,elem):
		return elem[0]

	def run(self):
		processCnt = multiprocessing.cpu_count()
		print("Available Processors: " + str(processCnt))

		startLine,bucketHeight = self.getBucket(processCnt)
		jobs = []
		jobsQueue = multiprocessing.Queue()

		for i in range(processCnt):
			job = RenderProcess(jobsQueue,i,self.width,self.height,startLine[i],bucketHeight,self.scene,self.cam)
			jobs.append(job)

		timerStart = datetime.now()
		for each in jobs:
			each.start()

		bucketArrays = [jobsQueue.get() for each in jobs]
		#This has to be after Queue.get() or simply don't join
		#Update: join() --- wait till all the processes finish, then move on
		for each in jobs:
			each.join()

		timerEnd = datetime.now()
		renderTime = timerEnd- timerStart
		print("Total Render Time: " + str(renderTime))

		bucketArrays.sort(key = self.getOrderKey)
		bucketArrays = [r[1] for r in bucketArrays]

		#merge the arrays into one
		mergedArrays = numpy.vstack(bucketArrays) #merged along second axis
		#numpy.require(mergedArrays,numpy.float32,"C")

		#convert array to QImage
		newImage = QImage(mergedArrays.data,self.width,self.height,mergedArrays.strides[0],QImage.Format_RGB888)
		newImage.save("test.png") #Image has to be save in this thread
		self.updateImgSignal.emit(newImage)
		# self.update(newImage)
