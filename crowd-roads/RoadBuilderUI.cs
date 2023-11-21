using System.Collections.Generic;
using UnityEngine;
using EasyRoads3Dv3;
using Michsky.MUIP;
using System;
using System.Linq;
using ITS.Utils;
using UnityEngine.EventSystems;
using System.Reflection.Emit;

public class RoadBuilderUI : MonoBehaviour
{
    public CustomDropdown elementPickerDropdown;
    public ButtonManager startButton, stopButton;
    public Plane plane;

    private bool dragging = false;
    private Vector3 endCoord;
    private ERRoad currentRoad;
    private ERConnection currentCrossing;
    private GameObject currentTrafficLight, currentTrafficSpawner;
    private int rotationDegree = 0;
    private Collider coll;
    private RoadBuilder roadBuilder;

    void Start()
    {
        coll = GetComponent<Collider>();
        roadBuilder = GetComponent<RoadBuilder>();

        startButton.onClick.AddListener(roadBuilder.StartSimulation);
        stopButton.onClick.AddListener(roadBuilder.StopSimulation);
    }

    void Update()
    {
        Vector3? coord = GetMouseWorldCoord();
        if (coord != null)
        {
            endCoord = SnapToGrid((Vector3)coord);
            if (dragging)
            {
                if (currentRoad != null)
                {
                    roadBuilder.UpdateRoadEndCoord(currentRoad, endCoord);
                }
                else if (currentCrossing != null)
                {
                    roadBuilder.UpdateCrossingCoord(currentCrossing, endCoord, rotationDegree);
                }
                else if (currentTrafficLight != null)
                {
                    roadBuilder.UpdateTrafficLightCoord(currentTrafficLight, endCoord, rotationDegree);
                }
                else if (currentTrafficSpawner != null)
                {
                    roadBuilder.UpdateTrafficSpawnerRadius(currentTrafficSpawner, endCoord);
                }
            }
        }

        if (Input.GetKeyDown(KeyCode.DownArrow))
        {
            rotationDegree = (rotationDegree + 90) % 360;
        }
        else if (Input.GetKeyDown(KeyCode.UpArrow))
        {
            rotationDegree = (rotationDegree - 90) % 360;
        }
    }

    void OnMouseDown()
    {
        if (EventSystem.current.IsPointerOverGameObject())
        {
            return;
        }

        dragging = true;
        Vector3? startCoord = GetMouseWorldCoord();
        if (startCoord != null)
        {
            Vector3 coord = SnapToGrid((Vector3)startCoord);
            switch (elementPickerDropdown.selectedText.text)
            {
                case "Two-way Road":
                    ERRoadType twoWayRoadType = roadBuilder.roadNetwork.GetRoadTypeByName("2Lane-2Way");
                    currentRoad = roadBuilder.CreateRoad("2w2lnRoad", twoWayRoadType, coord, 6f);
                    break;
                case "Two-way Road (4 lanes)":
                    ERRoadType twoWayFourLanesRoadType = roadBuilder.roadNetwork.GetRoadTypeByName("4Lane-2Way");
                    currentRoad = roadBuilder.CreateRoad("2w4lnRoad", twoWayFourLanesRoadType, coord, 6f);
                    break;
                case "One-way Road (2 lanes)":
                    ERRoadType oneWayTwoLanesRoadType = roadBuilder.roadNetwork.GetRoadTypeByName("2Lane-1Way");
                    currentRoad = roadBuilder.CreateRoad("1w2lnRoad", oneWayTwoLanesRoadType, coord, 6f);
                    break;
                case "X Intersection":
                    rotationDegree = 0;
                    currentCrossing = roadBuilder.CreateCrossing(RoadBuilder.ConnectionType.CrossingXTwoLane, coord);
                    break;
                case "T Intersection":
                    rotationDegree = 0;
                    currentCrossing = roadBuilder.CreateCrossing(RoadBuilder.ConnectionType.CrossingTTwoLane, coord);
                    break;
                case "X Intersection (4 lanes)":
                    rotationDegree = 0;
                    currentCrossing = roadBuilder.CreateCrossing(RoadBuilder.ConnectionType.CrossingXFourLane, coord);
                    break;
                case "T Intersection (4 lanes)":
                    rotationDegree = 0;
                    currentCrossing = roadBuilder.CreateCrossing(RoadBuilder.ConnectionType.CrossingTFourLane, coord);
                    break;
                case "Traffic Light":
                    rotationDegree = 0;
                    currentTrafficLight = roadBuilder.CreateTrafficLight(coord);
                    break;
                case "Traffic Spawner":
                    currentTrafficSpawner = roadBuilder.CreateTrafficSpawner(coord);
                    break;
            }
        }
    }

    void OnMouseUp()
    {
        dragging = false;

        if (currentRoad != null)
        {
            roadBuilder.ProcessNewRoad(currentRoad);
        }
        else if (currentCrossing != null)
        {
            roadBuilder.ProcessNewConnection(currentCrossing);
        }

        currentRoad = null;
        currentCrossing = null;
        currentTrafficLight = null;
        currentTrafficSpawner = null;
    }

    private Vector3? GetMouseWorldCoord()
    {
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        if (coll.Raycast(ray, out RaycastHit hit, 1000.0f))
        {
            Vector3 point = ray.GetPoint(hit.distance);
            point.y = 0.0f;
            return point;
        }

        return null;
    }

    private Vector3 SnapToGrid(Vector3 pos)
    {
        float factor = 2f;
        return new Vector3(Mathf.Round(pos.x / factor) * factor,
                             pos.y,
                             Mathf.Round(pos.z / factor) * factor);
    }
}
