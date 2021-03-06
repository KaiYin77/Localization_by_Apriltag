#!/usr/bin/env python2

from numpy.core.defchararray import count
from numpy.lib.financial import nper
import rospy
import numpy as np
import message_filters
import cv2
from cv_bridge import CvBridge, CvBridgeError
from darknet_ros_msgs.msg import BoundingBoxes
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PointStamped
from nav_msgs.msg import Odometry
import tf
from tf.transformations import quaternion_matrix, translation_matrix
from tf import transformations
import math
import os
import sys

pub = rospy.Publisher('/object_pose', PointStamped, queue_size=10)
pub1 = rospy.Publisher('/camera_pose', PointStamped, queue_size=10)
rospy.init_node('drone_Object', anonymous=True)
rospy.loginfo("Start D435_Object_Distance")
cv_bridge = CvBridge()

print('Try to get camera info...')

msg = rospy.wait_for_message('/camera/color/camera_info', CameraInfo, timeout=None)
#     [fx'  0  cx' Tx]
# P = [ 0  fy' cy' Ty]
#     [ 0   0   1   0]
print('Get camera info')
fx = msg.P[0]
fy = msg.P[5]
cx = msg.P[2]
cy = msg.P[6]

transform_time = 0.0
transform = Odometry()

Umbrella = np.zeros(3)
Bicycle = np.zeros(3)
TeddyBear =  np.zeros(3)
Chair = np.zeros(3)

Umbrella_output = np.array([])
Bicycle_output = np.array([])
TeddyBear_output =  np.array([])
Chair_output = np.array([])

def main():
    depth_image_sub = message_filters.Subscriber('/camera/aligned_depth_to_color/image_raw', Image) # ('???', ???)
    bb_sub = message_filters.Subscriber('/darknet_ros/bounding_boxes', BoundingBoxes) #('???', ???)
    ts = message_filters.ApproximateTimeSynchronizer([depth_image_sub, bb_sub], 10, 0.5) #(???, ???, ???)
    ts.registerCallback(callback) #(???)
    rospy.Subscriber("apriltag_localization", Odometry, transform_cb) #("???", ???, ???)
    rospy.spin()

def transform_cb(msg):
    global transform_time
    global transform
    transform_time = msg.header.stamp.to_sec()
    transform = msg
    # print("Get transform time")
    # print(transform_time)

def publish_object_location(object_position, depth_img, org, obj, class_type, bb_size):
    global Umbrella_output
    global Bicycle_output
    global TeddyBear_output
    global Chair_output
    # print(object_position/1000)
    point_message = PointStamped()
    point_message.header = depth_img.header
    point_message.header.frame_id = "origin"
    point_message.point.x = object_position[0]/1000 + org[0]
    point_message.point.y = object_position[1]/1000 + org[1]
    point_message.point.z = object_position[2]/1000 + org[2]
    # update obj
    obj[0] = object_position[0]/1000 + org[0]
    obj[1] = object_position[1]/1000 + org[1]
    obj[2] = object_position[2]/1000 + org[2]
    print('position:', obj[0], obj[1], obj[2])
    # append to array
    if class_type == "Umbrella":
        Umbrella_output = np.append(Umbrella_output,obj)
    elif class_type == "Bicycle":
        Bicycle_output = np.append(Bicycle_output,obj)
    elif class_type == "TeddyBear":
        TeddyBear_output = np.append(TeddyBear_output,obj)
    elif class_type == "Chair":
        Chair_output = np.append(Chair_output,obj)
    # print(Green_bottle_output.reshape(-1,3))
    # usage: reshape(-1,3) --> [[o,o,o][o,o,o][o,o,o]]
    submission_path = os.path.realpath('..') + "/output/drone_pkg"
    np.savez(submission_path ,
             a = Umbrella_output,
             b = Bicycle_output,
             c = TeddyBear_output,
             d = Chair_output)
    # print("npsave {0}",class_type)

def callback(depth_img, bb):
    global transform_time
    global transform
    local_time = depth_img.header.stamp.to_sec()
    print("Get local_time")
    print(local_time)
    print(transform_time)
    # print("Get local_time")
    # print(local_time)
    # you could set the time error2, 3, 4, 5 (local_time - transform_time) by yourself    
    if abs(local_time - transform_time) < 1 and transform_time != 0: #??? and transform_time != 0:
        print("Time error")
        print(local_time - transform_time)
        
        # hint: http://docs.ros.org/en/jade/api/tf/html/python/transformations.html
        # You could use "quaternion_matrix" function to find the 4x4 transform matrix
        global_transform = quaternion_matrix(np.array(
                                            [transform.pose.pose.orientation.x, 
                                             transform.pose.pose.orientation.y, 
                                             transform.pose.pose.orientation.z, 
                                             transform.pose.pose.orientation.w])) #(???)
        global_transform[0][3] = transform.pose.pose.position.x #???
        global_transform[1][3] = transform.pose.pose.position.y #???
        global_transform[2][3] = transform.pose.pose.position.z #???
        # print("transform")
        # print(global_transform)
        try:
            cv_depthimage = cv_bridge.imgmsg_to_cv2(depth_img, "32FC1")
            cv_depthimage2 = np.array(cv_depthimage, dtype=np.float32)
        except CvBridgeError as e:
            print(e)
        
        # publish camera pos in origin frame
        v1 = np.array([0,0,0,1])
        org = np.matmul(global_transform, v1)
        # print("camera_link")
        # print(object_position)
        point_message = PointStamped()
        point_message.header = depth_img.header
        point_message.header.frame_id = "origin"
        point_message.point.x = org[0]
        point_message.point.y = org[1]
        point_message.point.z = org[2]
        pub1.publish(point_message)
        
        for i in bb.bounding_boxes:

            x_mean = (i.xmax + i.xmin) / 2
            y_mean = (i.ymax + i.ymin) / 2
            bb_size = (i.xmax - i.xmin)*(i.ymax - i.ymin)
            thr = 10
            if (i.xmax>(640-thr) or i.xmin<thr or i.ymax>(480-thr) or i.ymin<thr) and i.Class != "umbrella":
                # if i.Class == "umbrella":
                #     print("umbrella")
                continue

            if i.Class == "umbrella" and i.probability >= 0.6:
                rospy.loginfo("see Umbrella")
                zc = cv_depthimage2[int(y_mean) - 30][int(x_mean)]
                v1 = np.array(getXYZ(x_mean - 30, y_mean, zc, fx, fy, cx, cy))
                object_position = np.matmul(global_transform, v1)
                publish_object_location(object_position,depth_img, org, Umbrella, "Umbrella", bb_size)
                
            elif i.Class == "bicycle" and i.probability >= 0.4 and bb_size > 90000:
                rospy.loginfo("see Bicycle")
                zc = cv_depthimage2[int(y_mean) + 65][int(x_mean)]
                v1 = np.array(getXYZ(x_mean, y_mean + 65, zc, fx, fy, cx, cy))
                object_position = np.matmul(global_transform, v1)
                publish_object_location(object_position,depth_img, org, Bicycle, "Bicycle", bb_size)
                
            elif i.Class == "teddy bear":
                rospy.loginfo("see TeddyBear")
                zc = cv_depthimage2[int(y_mean) + 10][int(x_mean)]
                v1 = np.array(getXYZ(x_mean, y_mean + 10, zc, fx, fy, cx, cy))
                object_position = np.matmul(global_transform, v1)
                publish_object_location(object_position,depth_img, org, TeddyBear, "TeddyBear", bb_size)
                                
            elif i.Class == "chair" and i.probability >= 0.4:
                rospy.loginfo("see Chair")
                zc = cv_depthimage2[int(y_mean)][int(x_mean)]
                v1 = np.array(getXYZ(x_mean, y_mean, zc, fx, fy, cx, cy))
                object_position = np.matmul(global_transform, v1)
                publish_object_location(object_position,depth_img, org, Chair, "Chair", bb_size)
            ############################
            #  Student Implementation  #
            ############################

def getXYZ(xp, yp, zc, fx, fy, cx, cy):
    #### Definition:
    # cx, cy : image center(pixel)
    # fx, fy : focal length
    # xp, yp: index of the depth image
    # zc: depth
    inv_fx = 1.0/fx
    inv_fy = 1.0/fy
    x = (xp-cx) *  zc * inv_fx
    y = (yp-cy) *  zc * inv_fy
    z = zc
    return (x,y,z,1.0)

if __name__ == '__main__':
    main()
