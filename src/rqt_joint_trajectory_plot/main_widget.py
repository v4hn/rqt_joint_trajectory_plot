#!/usr/bin/env python

from python_qt_binding import loadUi
from python_qt_binding.QtCore import Qt, QTimer, qWarning, Signal, Slot
from python_qt_binding.QtGui import QAction, QIcon, QMenu, QWidget, QTreeWidgetItem
import rospy, rospkg, roslib
from rqt_py_common import topic_helpers
from trajectory_msgs.msg import JointTrajectory
import numpy as np
from .plot_widget import PlotWidget

class MainWidget(QWidget):
    draw_curves = Signal(object, object)
    def __init__(self):
        super(MainWidget, self).__init__()
        self.setObjectName('MainWidget')

        rospack = rospkg.RosPack()
        ui_file = rospack.get_path('rqt_joint_trajectory_plot')+'/resource/JointTrajectoryPlot.ui'
        loadUi(ui_file, self)

        self.refresh_button.setIcon(QIcon.fromTheme('reload'))
        self.pause_button.setIcon(QIcon.fromTheme('media-playback-pause'))

        self.handler = None
        self.joint_names = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.plot_widget = PlotWidget(self)
        self.plot_layout.addWidget(self.plot_widget)
        self.draw_curves.connect(self.plot_widget.draw_curves)

        self.time = None
        (self.dis, self.vel, self.acc, self.eff) = ({}, {}, {}, {})

        # refresh topics list in the combobox
        self.refresh_topics()
        self.change_topic()

        self.refresh_button.clicked.connect(self.refresh_topics)
        self.topic_combox.currentIndexChanged.connect(self.change_topic)
        self.select_tree.itemChanged.connect(self.update_checkbox)

    def refresh_topics(self):
        '''
        Refresh topic list in the combobox
        '''
        topic_list = rospy.get_published_topics()
        if topic_list is None:
            return
        self.topic_combox.clear()
        for (name, type) in topic_list:
            if type == 'trajectory_msgs/JointTrajectory':
                self.topic_combox.addItem(name)

    def change_topic(self):
        topic_name = self.topic_combox.currentText()
        if not topic_name:
            return
        if self.handler:
            self.handler.unregister()
        self.joint_names = []
        self.handler = rospy.Subscriber(topic_name, JointTrajectory, self.callback)

    def close(self):
        if self.handler:
            self.handler.unregister()
            self.handler = None

    def refresh_tree(self):
        self.select_tree.itemChanged.disconnect()
        self.select_tree.clear()
        for joint_name in self.joint_names:
            item = QTreeWidgetItem(self.select_tree)
            item.setText(0, joint_name)
            item.setCheckState(0, Qt.Unchecked)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            for traj_name in ['position', 'velocity', 'acceleration', 'effort']:
                sub_item = QTreeWidgetItem(item)
                sub_item.setText(0, traj_name)
                sub_item.setCheckState(0, Qt.Unchecked)
                sub_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        self.select_tree.itemChanged.connect(self.update_checkbox)

    def callback(self, msg):
        if self.pause_button.isChecked():
            return
        self.time = np.array([0.0]*len(msg.points))
        (self.dis, self.vel, self.acc, self.eff) = ({}, {}, {}, {})
        for joint_name in msg.joint_names:
            self.dis[joint_name] = np.array([0.0]*len(msg.points))
            self.vel[joint_name] = np.array([0.0]*len(msg.points))
            self.acc[joint_name] = np.array([0.0]*len(msg.points))
            self.eff[joint_name] = np.array([0.0]*len(msg.points))
        for i in range(len(msg.points)):
            point = msg.points[i]
            self.time[i] = point.time_from_start.to_sec()
            for j in range(len(msg.joint_names)):
                joint_name = msg.joint_names[j]
                if point.positions:
                    self.dis[joint_name][i] = point.positions[j]
                if point.velocities:
                    self.vel[joint_name][i] = point.velocities[j]
                if point.accelerations:
                    self.acc[joint_name][i] = point.accelerations[j]
                if point.effort:
                    self.eff[joint_name][i] = point.effort[j]
        if self.joint_names != msg.joint_names:
            self.joint_names = msg.joint_names
            self.refresh_tree()
        self.joint_names = msg.joint_names
        self.plot_graph()

    def plot_graph(self):
        '''
        Emit changed signal to call plot_widet.draw_curves()
        '''
        curve_names = []
        data = {}
        data_list = [self.dis, self.vel, self.acc, self.eff]
        traj_names = ['position', 'velocity', 'acceleration', 'effort']
        # Create curve name and data from checked items
        for i in range(self.select_tree.topLevelItemCount()):
            joint_item = self.select_tree.topLevelItem(i)
            for n in range(len(traj_names)):
                item = joint_item.child(n)
                if item.checkState(0):
                    joint_name = joint_item.text(0)
                    curve_name = joint_name + ' ' + traj_names[n]
                    curve_names.append(curve_name)
                    data[curve_name] = (self.time, data_list[n][joint_name])
        self.draw_curves.emit(curve_names, data)

    def update_checkbox(self, item, column):
        self.recursive_check(item)
        self.plot_graph()

    def recursive_check(self, item):
        check_state = item.checkState(0)
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, check_state)
            self.recursive_check(item.child(i))
