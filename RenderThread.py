import multiprocessing, json, math
import numpy as np
from random import shuffle
from datetime import datetime
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from RenderProcess import RenderProcess

class RenderThread(QThread):
	#This is a separate thread from UI, this thread will spawn tasks to multi processing
	#This thread itself will be rendering as well
	updateImgSignal =pyqtSignal(list)

	def __init__(self,width,height,scene,cam):
		QThread.__init__(self)
		self.width = width
		self.height = height
		self.scene = scene
		self.cam = cam
		self.canvas = np.ndarray(shape=(self.height,self.width,3),dtype = np.float)
		self.canvas.fill(0) # Very important, need to set default color
		threadSettings = self.loadSettings()
		self.bucketSize = threadSettings["BucketSize"]
		self.bucketOrder = threadSettings["BucketOrder"]

	def loadSettings(self):
		with open("RenderSettings.json") as settingsData:
			renderSettings = json.load(settingsData)

		return renderSettings["RenderThread"]

	def getBucket(self):
		manager = multiprocessing.Manager()
		#input the bukcetSize, return a list of bucket Data
		#bucketSplitData = [[bucketPosX, bucketPosY, AAcnt].......]
		bucketHcnt = int(self.height / self.bucketSize)
		bucketWcnt = int(self.width / self.bucketSize)

		bucketSplitData = manager.list()
		for y in range(0,bucketHcnt):
			for x in range(0,bucketWcnt):
				newBucketSplit = [x*self.bucketSize,y*self.bucketSize,0]
				bucketSplitData.append(newBucketSplit)

		#Shuffle the buckets
		if self.bucketOrder == 1:
			#Buckets in random order:
			shuffle(bucketSplitData)
		elif self.bucketOrder == 2:
			#Buckets start from the center
			currIndex = math.floor(len(bucketSplitData)/2 - bucketHcnt/2- 1)
			shuffledBucketList = manager.list()
			shuffledBucketList.append(bucketSplitData[currIndex])
			stepAmount = 1
			stepLimit = 0
			stepDir = 0
			switchList = [1,bucketHcnt,-1,-bucketHcnt] #move right,down,left,up
			while len(shuffledBucketList) < len(bucketSplitData):
				for i in range(stepAmount):
					#each Step
					currIndex += switchList[stepDir]
					shuffledBucketList.append(bucketSplitData[currIndex])

				if stepDir < 3:
					stepDir += 1
				else:
					stepDir = 0

				stepLimit += 1

				if stepLimit == 2:
					stepAmount += 1
					stepLimit = 0

			bucketSplitData = shuffledBucketList

		return bucketSplitData

	def run(self):
		processCnt = multiprocessing.cpu_count()
		print("Available Processors: " + str(processCnt))

		bucketPosData = self.getBucket() #multiprocessing manager list

		jobs = []
		jobsQueue = multiprocessing.Queue()

		bucktCntLock = multiprocessing.Lock()
		bucketCnt = multiprocessing.Value('i',0)

		for i in range(processCnt):
			job = RenderProcess(jobsQueue,self.width,self.height,bucketPosData,bucketCnt,bucktCntLock,self.bucketSize,self.scene,self.cam)
			jobs.append(job)

		timerStart = datetime.now()
		for each in jobs:
			each.start()

		processGetCnt = 0
		while True:
			bucketDataSet = jobsQueue.get() #block until an item is available

			if bucketDataSet == "Done":
				processGetCnt = processGetCnt + 1
			else:
				#stamp bucket array onto the canvas array
				dataX = bucketDataSet[0]
				dataY = bucketDataSet[1]
				self.canvas[dataY:dataY+self.bucketSize,dataX:dataX+self.bucketSize] *= (bucketDataSet[3] - 1)
				self.canvas[dataY:dataY+self.bucketSize,dataX:dataX+self.bucketSize] += bucketDataSet[2]
				self.canvas[dataY:dataY+self.bucketSize,dataX:dataX+self.bucketSize] /= bucketDataSet[3]

				#Clamp color to [0,1] and apply 2.2 gamma correction and convert sRGB,
				#in order to convert it to Qimage, array type has to be uint8
				bucketBufferArray = self.canvas[dataY:dataY+self.bucketSize,dataX:dataX+self.bucketSize]
				bucketBufferArray = (np.power(np.clip(bucketBufferArray,0,1),1/2.2) * 255).astype(np.uint8)

				#convert array to QImage
				bucketBufferImage = QImage(bucketBufferArray.data,self.bucketSize,self.bucketSize,bucketBufferArray.strides[0],QImage.Format_RGB888)
				self.updateImgSignal.emit([dataX,dataY,bucketBufferImage])
				print("bucketCnt",bucketCnt.value)

			if processGetCnt>= processCnt:
				break

		#This has to be after Queue.get() or simply don't join
		#Update: join() --- wait till all the processes finish, then move on
		# for each in jobs:
		# 	each.join()

		timerEnd = datetime.now()
		renderTime = timerEnd - timerStart
		print("Total Render Time: " + str(renderTime))
