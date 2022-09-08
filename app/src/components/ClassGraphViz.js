import React, { useCallback, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import Grid from '@material-ui/core/Grid'
import Dialog from '@material-ui/core/Dialog'
import DialogContent from '@material-ui/core/DialogContent'
import Typography from '@material-ui/core/Typography'
import CircularProgress from '@material-ui/core/CircularProgress'
import ArrowRightAltIcon from '@material-ui/icons/ArrowRightAlt'
import AutorenewIcon from '@material-ui/icons/Autorenew'
import IconButton from '@material-ui/core/IconButton'
import CloseIcon from '@material-ui/icons/Close'
import Tooltip from '@material-ui/core/Tooltip'

import ForceGraph2D from 'react-force-graph-2d'
import { SizeMe } from 'react-sizeme'
import * as d3 from 'd3'

import GraphSearch from './GraphSearch'
import useStyles from '../styles/graph'


const ClassGraphViz = ({ data, loading, hideClassGraphViz, size }) => {

  const fgRef = useRef()

  const { id } = useParams()

  const classes = useStyles()

  const [hoverNode, setHoverNode] = useState(null)
  const [highlightNodes, setHighlightNodes] = useState(new Set())
  const [highlightLinks, setHighlightLinks] = useState(new Set())

  const updateHighlight = () => {
    setHighlightNodes(highlightNodes)
    setHighlightLinks(highlightLinks)
  }

  const handleNodeHover = node => {
    highlightNodes.clear()
    highlightLinks.clear()
    if (node) {
      highlightNodes.add(node)

      data.links.forEach(link => {
      })

      node.neighbors.forEach(neighbor => highlightNodes.add(neighbor))
      node.links.forEach(link => highlightLinks.add(link))
    }

    setHoverNode(node || null)
    updateHighlight()
  }

  const handleLinkHover = link => {
    highlightNodes.clear()
    highlightLinks.clear()

    if (link) {
      highlightLinks.add(link)
      highlightNodes.add(link.source)
      highlightNodes.add(link.target)
    }

    updateHighlight()
  }

  const resetGraph = () => {
    fgRef.current.zoomToFit(500, 50)
    fgRef.current.d3ReheatSimulation()
  }

  const selectNode = useCallback(node => {
    let url = `/${node.id}`

    // prefix the url with the location of where the app is hosted
    if ( process.env.REACT_APP_FRONTEND_URL ) {
      url = `${process.env.REACT_APP_FRONTEND_URL}${url}`
    }

    window.location = url
  }, [fgRef])

  const centerOnNode = useCallback(node => {
    if ( !node ) { return }
    fgRef.current.zoomToFit(500, 50)
    fgRef.current.d3ReheatSimulation()
    fgRef.current.centerAt(node.x, node.y, 1000)
  }, [fgRef])

  const getNodeColor = node => {
    if ( node.color[0] === '#' ) {
      return node.color
    }
    return d3.schemeCategory10[node.color]
  }

  const renderNodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const label = node.label
    const fontSize = 12 / globalScale
    ctx.font = `${fontSize}px Sans-Serif`
    const textWidth = ctx.measureText(label).width
    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2) // some padding

    // add outline for the highlighted node
    ctx.beginPath()
    ctx.arc(node.x, node.y, node.size * 1.4, 0, 2 * Math.PI, false)
    ctx.fillStyle = node === hoverNode ? '#d62728' : getNodeColor(node)
    ctx.fill()

    // render node labels only for nodes with incoming edges
    // in which case showLabel = true
    if ( node.showLabel ) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.85)'
      ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - (node.size + 5) - bckgDimensions[1] / 2, ...bckgDimensions)

      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'

      ctx.fillStyle = getNodeColor(node)
      if ( node.id === id ) {
        ctx.fillStyle = 'limegreen'
      }

      ctx.fillText(label, node.x, node.y - (node.size + 5))
    } else {
      ctx.fillStyle = getNodeColor(node)
      if ( node.id === id ) {
        ctx.fillStyle = 'limegreen'
      }
    }

    ctx.beginPath()
    ctx.arc(node.x, node.y, node.size, 0, 2 * Math.PI, false)
    ctx.fill()

    node.__bckgDimensions = bckgDimensions // to re-use in nodePointerAreaPaint
  }, [hoverNode])

  const renderGraph = () => {
    if ( !data ) { return }
    return (
      <SizeMe
        refreshRate={32}
        monitorWidth={true}
        monitorHeight={true}
        noPlaceholder={true}
        render={({ size }) => (
          <ForceGraph2D
            ref={fgRef}
            graphData={data}
            cooldownTime={25000}
            nodeId={'id'}
            nodeLabel={'tooltip'}
            nodeVal={'size'}

            width={size.width}
            height={size.height}

            nodeColor={node => getNodeColor(node)}

            onNodeClick={selectNode}
            onNodeHover={handleNodeHover}
            onLinkHover={handleLinkHover}

            linkWidth={link => highlightLinks.has(link) ? 3 : 1}

            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}

            linkColor={link => getNodeColor(link)}

            nodeCanvasObject={renderNodeCanvasObject}

          />
        )}
      />
    )
  }

  const renderLoading = () => {
    if ( !loading ) { return }
    return (
      <CircularProgress
        size={50}
        color="inherit"
        className={classes.loading} />
    )
  }

  const renderLegend = () => {
    return (
      <div className={classes.legend}>
        <h3>Legend</h3>
        <p><div className={classes.rootNode} /> Root Node</p>
        <p><div className={classes.orangeNode} /> Many Subclasses</p>
        <p><div className={classes.blueNode} /> Few Subclasses</p>
        <p><ArrowRightAltIcon className={classes.superclass} /> Superclass</p>
        <p><ArrowRightAltIcon className={classes.subclass} /> Subclass</p>
      </div>
    )
  }

  const renderToolbar = () => {
    if ( !data || !data.nodes ) { return }
    return (
      <Grid container spacing={1} className={classes.toolbar}>
        <Grid item xs={9}>
          <GraphSearch
            nodes={data.nodes}
            onSelect={node => centerOnNode(node)} />
        </Grid>
        <Grid item xs={1}>
          <Tooltip arrow title="Reset Graph">
            <IconButton
              color="inherit"
              title="Reset Graph"
              onClick={resetGraph}>
              <AutorenewIcon fontSize="large" />
            </IconButton>
          </Tooltip>
        </Grid>
        <Grid item xs={1}>
        </Grid>
        <Grid item xs={1}>
          <Tooltip arrow title="Close Graph">
            <IconButton
              color="inherit"
              title="Close Graph"
              onClick={hideClassGraphViz}>
              <CloseIcon fontSize="large" />
            </IconButton>
          </Tooltip>
        </Grid>
      </Grid>
    )
  }

  const renderTitle = () => {
    return (
      <Typography variant="h6" className={classes.title}>
        Class Graph Visualization
      </Typography>
    )
  }

  const renderContent = () => {
    return (
      <Grid container spacing={1} className={classes.wrapper}>
        {renderTitle()}
        {renderLegend()}
        {renderToolbar()}
        <Grid item xs={12}>
          {renderLoading()}
          {renderGraph()}
        </Grid>
      </Grid>
    )
  }

  return (
    <Dialog
      open={true}
      maxWidth={'xl'}
      onClose={hideClassGraphViz}
      classes={{paper: classes.dialog}}>
      <DialogContent>
        {renderContent()}
      </DialogContent>
    </Dialog>
  )
}


export default ClassGraphViz
